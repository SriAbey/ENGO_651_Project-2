# Project 1

ENGO 651 - Advanced Geospatial Topics

# Book Review Website

This is a web application for book reviews built using Python, Flask, and PostgreSQL. Users can register, log in, search for books, submit reviews, and view book details. The application integrates the Google Books API for additional book information and uses Google's Gemini API for book summarization. Additionally, a RESTful API is provided to fetch book details in JSON format.

## Features
- **User Authentication:** Register and log in securely.
- **Book Search:** Search books by title, author, or ISBN.
- **Book Reviews:** Submit and view reviews for books.
- **Google Books API Integration:** Fetch book details such as cover images and descriptions.
- **AI-Powered Summarization:** Uses Google's Gemini API to generate book summaries.
- **RESTful API:** Exposes book details and reviews via an API.

## Project Structure
```
static/
  images/
    background.png
    placeholder.png
  styles/
    layout_index.css
    register_login.css
    search_result_review.css

templates/
  layout.html
  index.html
  register.html
  login.html
  search.html
  review.html

requirements.txt  # Project dependencies
.env              # Environment variables (API keys, DB credentials)
import.py         # Script to import book data from books.csv
application.py    # Main Flask application
books.csv         # Dataset containing book information
```

## Installation and Setup
### Prerequisites
- Python (>=3.8)
- PostgreSQL
- Flask and dependencies

### Installation Steps
1. Clone the repository:
   ```sh
   git clone <repository-url>
   cd book-review-website
   ```
2. Create a virtual environment and install dependencies:
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Set up environment variables in a `.env` file:
   ```sh
   DATABASE_URL="your_postgresql_database_url"
   GOOGLE_BOOKS_API_KEY="your_google_books_api_key"
   ```
4. Import book data into the database:
   ```sh
   python import.py
   ```
5. Run the application:
   ```sh
   flask run
   ```

## Usage
1. Open `http://127.0.0.1:5000/` in your browser.
2. Register for an account and log in.
3. Search for books and view details.
4. Leave and read reviews for books.
5. Use the RESTful API to fetch book details.

## API Endpoints
- **GET /api/books/&lt;isbn&gt;**
  - Returns book details and reviews in JSON format.

## License
This project is licensed under the MIT License.

## Author
Sri Raji Abeywickrama

