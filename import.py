import csv
import os
import psycopg2
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    # Load database URL from environment variables
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        logging.error("DATABASE_URL environment variable is not set.")
        sys.exit(1)

    # Connect to PostgreSQL database using context manager
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                
                # Ensure books table exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS books (
                        isbn VARCHAR(20) PRIMARY KEY,
                        title TEXT NOT NULL,
                        author TEXT NOT NULL,
                        year INTEGER NOT NULL
                    );
                """)
                conn.commit()
                
                # Open the CSV file and read its contents
                try:
                    with open("books.csv", "r", encoding="utf-8") as file:
                        reader = csv.reader(file)
                        header = next(reader, None)  # Skip header row if it exists

                        if not header:
                            logging.error("The CSV file is empty.")
                            sys.exit(1)

                        data = []
                        skipped = 0

                        for row in reader:
                            try:
                                isbn, title, author, year = row
                                data.append((isbn.strip(), title.strip(), author.strip(), int(year.strip())))
                            except ValueError:
                                skipped += 1
                                logging.warning(f"Skipping malformed row: {row}")

                        logging.info(f"Total records read: {len(data) + skipped}, valid: {len(data)}, skipped: {skipped}")

                        if data:
                            cur.executemany(
                                "INSERT INTO books (isbn, title, author, year) VALUES (%s, %s, %s, %s) "
                                "ON CONFLICT (isbn) DO UPDATE SET title = EXCLUDED.title, "
                                "author = EXCLUDED.author, year = EXCLUDED.year",
                                data
                            )
                            conn.commit()
                            logging.info(f"Inserted/Updated {len(data)} records.")

                except FileNotFoundError:
                    logging.error("The file 'books.csv' was not found.")
                    sys.exit(1)
                except UnicodeDecodeError:
                    logging.error("Encoding error: Please ensure the CSV file is UTF-8 encoded.")
                    sys.exit(1)
                except Exception as e:
                    logging.error(f"An error occurred while processing the CSV file: {e}")
                    sys.exit(1)

    except psycopg2.Error as e:
        logging.error(f"Database error: {e}")
        sys.exit(1)

    logging.info("Books import completed successfully!")

if __name__ == "__main__":
    main()