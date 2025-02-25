from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from flask_session import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
import os
import requests
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database connection
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
db = scoped_session(sessionmaker(bind=engine))

def summarize_description(description):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(f"Summarize this text using less than 50 words: {description}")
    return response.text

def fetch_google_books_data(isbn):
    response = requests.get("https://www.googleapis.com/books/v1/volumes", params={"q": f"isbn:{isbn}"})
    if response.status_code == 200:
        data = response.json()
        if data.get("totalItems", 0) > 0:
            volume_info = data["items"][0]["volumeInfo"]
            return {
                "average_rating": volume_info.get("averageRating"),
                "ratings_count": volume_info.get("ratingsCount"),
                "description": volume_info.get("description"),
            }
    return None

# Home route
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name")[:100]  # Truncate to 100 characters
        email = request.form.get("email")[:100]  # Truncate to 100 characters
        username = request.form.get("username")[:50]  # Truncate to 50 characters
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # Check if passwords match
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("register"))

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Check if username or email already exists
        user_exists = db.execute(
            text("SELECT * FROM users WHERE username = :username OR email = :email"),
            {"username": username, "email": email}
        ).fetchone()

        if user_exists:
            flash("Username or email already exists!", "danger")
            return redirect(url_for("register"))

        # Insert new user into the database
        try:
            db.execute(
                text("""
                    INSERT INTO users (full_name, email, username, password)
                    VALUES (:full_name, :email, :username, :password)
                """),
                {"full_name": full_name, "email": email, "username": username, "password": hashed_password}
            )
            db.commit()
        except Exception as e:
            db.rollback()
            flash("An error occurred during registration. Please try again.", "danger")
            return redirect(url_for("register"))

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email_username = request.form.get("email_username")
        password = request.form.get("password")

        # Fetch user from the database
        user = db.execute(
            text("SELECT * FROM users WHERE email = :email OR username = :username"),
            {"email": email_username, "username": email_username}
        ).fetchone()

        # Check if user exists and password is correct
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Login successful!", "success")
            return redirect(url_for("search"))
        else:
            flash("Invalid email/username or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

# Logout route
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))

# Search route
@app.route("/search", methods=["GET"])
def search():
    if not session.get("user_id"):
        flash("Please log in to search for books.", "warning")
        return redirect(url_for("login"))

    query = request.args.get("book")  # Use the correct query parameter name
    if query:
        # Search for books by title, author, or ISBN (partial matches)
        books = db.execute(
            text("""
                SELECT * FROM books
                WHERE title ILIKE :query OR author ILIKE :query OR isbn ILIKE :query
            """),
            {"query": f"%{query}%"}
        ).fetchall()

        # Render the search results template with the books and query
        return render_template("search.html", books=books, query=query)
    else:
        # If no query is provided, render the search page without results
        return render_template("search.html")

@app.route("/book/<isbn>", methods=["GET", "POST"])
def book(isbn):
    if request.method == "POST":
        # Ensure the user is logged in
        if not session.get("user_id"):
            flash("Please log in to submit a review.", "warning")
            return redirect(url_for("login"))

        # Get form data
        rating = request.form.get("rating")
        comment = request.form.get("comment")
        # Validate input
        if not rating or not comment:
            flash("Please provide both a rating and a comment.", "danger")
            return redirect(url_for("book", isbn=isbn))

        # Check if the user has already reviewed this book
        existing_review = db.execute(
            text("SELECT * FROM reviews WHERE user_id = :user_id AND book_isbn = :isbn"),
            {"user_id": session["user_id"], "isbn": isbn}
        ).fetchone()

        if existing_review:
            flash("You have already submitted a review for this book.", "danger")
            return redirect(url_for("book", isbn=isbn))

            # Save the review to the database
        try:
            db.execute(
                text("""
                    INSERT INTO reviews (user_id, book_isbn, rating, comment)
                    VALUES (:user_id, :book_isbn, :rating, :comment)
                """),
                {"user_id": session["user_id"], "book_isbn": isbn, "rating": rating, "comment": comment}
            )
            db.commit()
            flash("Your review has been submitted successfully!", "success")
        except Exception as e:
            db.rollback()
            flash("An error occurred while submitting your review. Please try again.", "danger")

        return redirect(url_for("book", isbn=isbn))


    # Fetch book details from the database
    book = db.execute(text("SELECT * FROM books WHERE isbn = :isbn"), {"isbn": isbn}).fetchone()
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("search"))

    # Fetch Google Books API data
    google_books_data = fetch_google_books_data(isbn)
    average_rating = google_books_data.get("average_rating") if google_books_data else None
    ratings_count = google_books_data.get("ratings_count") if google_books_data else None
    description = google_books_data.get("description") if google_books_data else None

    # Summarize description using Gemini API
    summarized_description = summarize_description(description) if description else None

    # Fetch reviews from the database
    reviews = db.execute(
        text("SELECT reviews.*, users.username FROM reviews JOIN users ON reviews.user_id = users.id WHERE book_isbn = :isbn"),
        {"isbn": isbn}
    ).fetchall()

    return render_template(
        "review.html",
        book=book,
        reviews=reviews,
        average_rating=average_rating,
        ratings_count=ratings_count,
        description=description,
        summarized_description=summarized_description,
    )

@app.route("/api/<isbn>", methods=["GET"])
def api_book(isbn):
    # Fetch book details from the database
    book = db.execute(text("SELECT * FROM books WHERE isbn = :isbn"), {"isbn": isbn}).fetchone()
    if not book:
        return jsonify({"error": "Book not found"}), 404

    # Fetch Google Books API data
    google_books_data = fetch_google_books_data(isbn)
    average_rating = google_books_data.get("average_rating") if google_books_data else None
    ratings_count = google_books_data.get("ratings_count") if google_books_data else None
    description = google_books_data.get("description") if google_books_data else None

    # Summarize description using Gemini API
    summarized_description = summarize_description(description) if description else None

    # Prepare JSON response
    response = {
        "title": book.title,
        "author": book.author,
        "publishedDate": book.year,
        "ISBN_10": book.isbn,  # Assuming ISBN_10 is stored in the database
        "ISBN_13": None,  # You can fetch ISBN_13 from Google Books API if needed
        "reviewCount": ratings_count,
        "averageRating": average_rating,
        "summarizedDescription": summarized_description,
    }

    return jsonify(response)

# Run the application
if __name__ == "__main__":
    app.run(debug=True)