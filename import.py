import os
import sys
import time
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import scoped_session, sessionmaker
import requests
from dotenv import load_dotenv
import logging
from typing import Optional, Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class DatabaseImporter:
    """Handles database connection and data import operations"""
    
    def __init__(self):
        self.engine = self._create_engine_with_retry()
        self.db = scoped_session(sessionmaker(bind=self.engine))
        
    def _create_engine_with_retry(self, max_retries: int = 3, retry_delay: int = 5):
        """Create database connection with retry logic"""
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:950813@localhost:5432/optiroute_db')
        
        for attempt in range(max_retries):
            try:
                engine = create_engine(
                    db_url,
                    pool_size=10,
                    max_overflow=20,
                    pool_recycle=3600,
                    pool_pre_ping=True
                )
                # Test connection
                with engine.connect() as conn:
                    conn.execute("SELECT 1")
                logger.info("Database connection established")
                return engine
            except exc.SQLAlchemyError as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        logger.error("Failed to establish database connection after retries")
        raise RuntimeError("Database connection failed")

    def create_tables(self) -> bool:
        """Create required database tables"""
        table_definitions = [
            """
            CREATE TABLE IF NOT EXISTS users_geo (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(100) NOT NULL,
                first_name VARCHAR(50) NOT NULL,
                last_name VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS hospitals_clinics (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                address VARCHAR(200) NOT NULL,
                comm_code VARCHAR(20) NOT NULL UNIQUE,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                CONSTRAINT valid_coordinates CHECK (
                    (latitude IS NULL AND longitude IS NULL) OR
                    (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
                )
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reviews_geo (
                id SERIAL PRIMARY KEY,
                rate INTEGER NOT NULL CHECK (rate BETWEEN 1 AND 5),
                comment TEXT NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users_geo(id) ON DELETE CASCADE,
                hospital_clinic_id INTEGER NOT NULL REFERENCES hospitals_clinics(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, hospital_clinic_id)
            )
            """
        ]
        
        try:
            for table in table_definitions:
                self.db.execute(table)
            self.db.commit()
            logger.info("Database tables created successfully")
            return True
        except exc.SQLAlchemyError as e:
            logger.error(f"Error creating tables: {str(e)}")
            self.db.rollback()
            return False

    def fetch_hospital_data(self) -> Optional[Dict]:
        """Fetch hospital data from Calgary's open data API"""
        url = "https://data.calgary.ca/resource/x34e-bcjz.geojson"
        params = {
            "$where": "type='PHS Clinic' or type='Hospital'",
            "$limit": 1000,
            "$select": "name,type,address,comm_code,latitude,longitude"
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if not isinstance(data.get('features'), list):
                raise ValueError("Invalid data format: missing features list")
                
            logger.info(f"Fetched {len(data['features'])} hospital records")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching hospital data: {str(e)}")
        except ValueError as e:
            logger.error(f"Data validation error: {str(e)}")
            
        return None

    def import_hospital_data(self, data: Dict) -> bool:
        """Import hospital data into database"""
        if not data or not isinstance(data.get('features'), list):
            logger.error("No valid hospital data to import")
            return False

        batch_size = 50
        success_count = 0
        batch = []
        
        for feature in data['features']:
            try:
                properties = feature.get('properties', {})
                geometry = feature.get('geometry', {})
                
                # Validate required fields
                required = {
                    'name': properties.get('name'),
                    'type': properties.get('type'),
                    'address': properties.get('address'),
                    'comm_code': properties.get('comm_code')
                }
                
                if None in required.values():
                    logger.warning(f"Skipping incomplete record: {properties}")
                    continue
                
                # Get coordinates
                coords = geometry.get('coordinates', [None, None])
                
                batch.append({
                    **required,
                    'longitude': coords[0],
                    'latitude': coords[1]
                })
                
                # Insert in batches
                if len(batch) >= batch_size:
                    self._insert_batch(batch)
                    success_count += len(batch)
                    batch = []
                    
            except Exception as e:
                logger.error(f"Error processing record: {properties} - {str(e)}")
                continue

        # Insert remaining records
        if batch:
            try:
                self._insert_batch(batch)
                success_count += len(batch)
            except Exception as e:
                logger.error(f"Error inserting final batch: {str(e)}")

        logger.info(f"Successfully imported {success_count} hospitals/clinics")
        return success_count > 0

    def _insert_batch(self, batch: List[Dict]) -> None:
        """Helper method to insert a batch of records"""
        self.db.execute(
            """INSERT INTO hospitals_clinics 
            (name, type, address, comm_code, longitude, latitude) 
            VALUES (
                :name, :type, :address, :comm_code, :longitude, :latitude
            )
            ON CONFLICT (comm_code) DO NOTHING""",
            batch
        )
        self.db.commit()

    def create_indexes(self) -> bool:
        """Create database indexes for better performance"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_hospitals_comm_code ON hospitals_clinics(comm_code)",
            "CREATE INDEX IF NOT EXISTS idx_hospitals_location ON hospitals_clinics(latitude, longitude)",
            "CREATE INDEX IF NOT EXISTS idx_reviews_hospital ON reviews_geo(hospital_clinic_id)"
        ]
        
        try:
            for index in indexes:
                self.db.execute(index)
            self.db.commit()
            logger.info("Database indexes created successfully")
            return True
        except exc.SQLAlchemyError as e:
            logger.error(f"Error creating indexes: {str(e)}")
            self.db.rollback()
            return False

    def run(self) -> bool:
        """Main execution method"""
        try:
            logger.info("Starting database setup...")
            
            if not self.create_tables():
                return False
                
            hospital_data = self.fetch_hospital_data()
            if not hospital_data:
                return False
                
            if not self.import_hospital_data(hospital_data):
                return False
                
            if not self.create_indexes():
                return False
                
            logger.info("Database setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Fatal error during setup: {str(e)}")
            return False
        finally:
            self.db.remove()

if __name__ == "__main__":
    importer = DatabaseImporter()
    if not importer.run():
        sys.exit(1)