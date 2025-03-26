import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_socketio import SocketIO, emit
from flask_jsglue import JSGlue
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime
import logging

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
jsglue = JSGlue(app)

# Configuration
class Config:
    SESSION_PERMANENT = False
    SESSION_TYPE = "filesystem"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql://postgres:950813@localhost:5432/optiroute_db")
    MAPBOX_ACCESS_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

app.config.from_object(Config)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# Initialize extensions
Session(app)
socketio = SocketIO(app, logger=True, engineio_logger=True)

# Database connection with connection pooling
def get_database_connection():
    return create_engine(
        app.config["SQLALCHEMY_DATABASE_URI"],
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True
    )

engine = get_database_connection()
db = scoped_session(sessionmaker(bind=engine))

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.remove()

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', 
                         message="Page not found",
                         type_error="generic"), 404

@app.errorhandler(500)
def internal_error(error):
    db.rollback()
    return render_template('error.html',
                         message="Internal server error",
                         type_error="generic"), 500

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username_login", "").strip()
        password = request.form.get("password_login", "").strip()

        if not username or not password:
            return render_template("error.html", 
                                message="Username and password cannot be empty",
                                type_error="login")

        user = db.execute(
            "SELECT id, password FROM users_geo WHERE username = :username",
            {"username": username}
        ).fetchone()

        if not user or not check_password_hash(user.password, password):
            return render_template("error.html",
                                message="Invalid username or password",
                                type_error="login")

        session["user_id"] = user.id
        session["username"] = username
        return redirect(url_for("mapping"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username_register", "").strip()
        password = request.form.get("password_register", "").strip()
        first_name = request.form.get("firstName", "").strip()
        last_name = request.form.get("lastName", "").strip()

        if not all([username, password, first_name, last_name]):
            return render_template("error.html",
                                message="All fields are required",
                                type_error="registration")

        if db.execute("SELECT 1 FROM users_geo WHERE username = :username",
                     {"username": username}).rowcount > 0:
            return render_template("error.html",
                                message="Username already exists",
                                type_error="registration")

        hashed_pw = generate_password_hash(password)
        db.execute(
            """INSERT INTO users_geo (username, password, first_name, last_name)
            VALUES (:username, :password, :first_name, :last_name)""",
            {
                "username": username,
                "password": hashed_pw,
                "first_name": first_name,
                "last_name": last_name
            }
        )
        db.commit()
        return render_template("success_submit.html", submit_type="register")

    return render_template("register.html")

@app.route("/map")
def mapping():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("search_hospital_clinic.html", 
                         username=session.get("username"),
                         mapbox_token=app.config["MAPBOX_ACCESS_TOKEN"])

@app.route("/direction/<loc_1>/<loc_2>")
def direction(loc_1, loc_2):
    try:
        # Validate coordinates
        start = loc_1.split(',')
        end = loc_2.split(',')
        
        if len(start) != 2 or len(end) != 2:
            raise ValueError("Invalid coordinate format")
            
        # Use OSRM routing engine
        url = f"http://router.project-osrm.org/route/v1/driving/{loc_1};{loc_2}?overview=full&steps=true&alternatives=3"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        return jsonify(response.json())
        
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Routing request failed: {str(e)}")
        return jsonify({"error": "Routing service unavailable"}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

# Socket.IO events
@socketio.on("read_data")
def read_json_data():
    try:
        # Hospital data
        hospitals_response = requests.get(
            "https://data.calgary.ca/resource/x34e-bcjz.geojson",
            params={
                "$where": "type='PHS Clinic' or type='Hospital'",
                "$limit": 1000,
                "$select": "name,type,address,comm_code,latitude,longitude"
            },
            timeout=10
        )
        hospitals_data = hospitals_response.json() if hospitals_response.status_code == 200 else {"features": []}

        # Traffic data
        traffic_response = requests.get(
            "https://data.calgary.ca/resource/qr97-4jvx.geojson",
            params={"$limit": 5000},
            timeout=10
        )
        traffic_data = traffic_response.json() if traffic_response.status_code == 200 else {"features": []}

        emit("map_data", {
            "traffics": traffic_data,
            "hospitals_clinics": hospitals_data
        })

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Data API error: {str(e)}")
        emit("map_error", {"message": "Failed to load map data"})

@app.route("/map/details/<code>")
def hospital_clinic_details(code):
    # Clear previous session data
    session.pop("hospital_clinic_id_code", None)
    
    hospital = db.execute(
        """SELECT h.*, 
           COUNT(r.id) as review_count,
           AVG(r.rate) as avg_rating
           FROM hospitals_clinics h
           LEFT JOIN reviews_geo r ON h.id = r.hospital_clinic_id
           WHERE h.comm_code = :code
           GROUP BY h.id""",
        {"code": code}
    ).fetchone()

    if not hospital:
        return render_template("error.html",
                            message="Hospital/clinic not found",
                            type_error="map")

    # Store both ID and code in session
    session["hospital_clinic_id_code"] = (hospital.id, code)
    
    reviews = db.execute(
        """SELECT u.username, r.rate, r.comment, r.created_at
        FROM reviews_geo r JOIN users_geo u ON r.user_id = u.id
        WHERE r.hospital_clinic_id = :id
        ORDER BY r.created_at DESC""",
        {"id": hospital.id}
    ).fetchall()

    return render_template("hospital_clinic_details.html",
                         hospital=hospital,
                         reviews=reviews)

@app.route("/map/details/submit-review", methods=["POST"])
def submit_review():
    if "user_id" not in session or "hospital_clinic_id_code" not in session:
        return redirect(url_for("login"))

    try:
        rating = int(request.form.get("rating"))
        comment = request.form.get("comment", "").strip()
        hospital_id, code = session["hospital_clinic_id_code"]

        if not rating or rating < 1 or rating > 5:
            raise ValueError("Invalid rating")

        # Check for existing review
        existing_review = db.execute(
            """SELECT 1 FROM reviews_geo 
            WHERE user_id = :uid AND hospital_clinic_id = :hid""",
            {"uid": session["user_id"], "hid": hospital_id}
        ).fetchone()

        if existing_review:
            raise ValueError("You already submitted a review")

        db.execute(
            """INSERT INTO reviews_geo 
            (rate, comment, user_id, hospital_clinic_id)
            VALUES (:rate, :comment, :uid, :hid)""",
            {
                "rate": rating,
                "comment": comment,
                "uid": session["user_id"],
                "hid": hospital_id
            }
        )
        db.commit()
        
        return render_template("success_submit.html",
                             submit_type="review",
                             code=code)

    except ValueError as e:
        return render_template("error.html",
                            message=str(e),
                            type_error="hospital_detail",
                            code=session["hospital_clinic_id_code"][1])
    except Exception as e:
        db.rollback()
        app.logger.error(f"Review submission error: {str(e)}")
        return render_template("error.html",
                            message="An error occurred",
                            type_error="hospital_detail",
                            code=session["hospital_clinic_id_code"][1])

if __name__ == "__main__":
    socketio.run(app, debug=True)