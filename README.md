
# FastAPI Authentication and Products API

This is a FastAPI-based project that implements a secure REST API with user authentication (using JWT tokens) and product management functionality. The application connects to a PostgreSQL database to store user and product data.

## Overview

- **Authentication**: Users can register, log in, and refresh tokens using OAuth2 with JWT.
- **Product Management**: Authenticated users can view and create products associated with their accounts.
- **Database**: Uses PostgreSQL with `psycopg2` for database operations.

## Features

- User registration with password hashing (bcrypt).
- Login to obtain access and refresh tokens.
- Token refresh endpoint for expired access tokens.
- Protected routes requiring valid JWT tokens.
- CRUD operations for products (currently GET and POST).

## Prerequisites

- Python 3.13
- PostgreSQL 17
- Virtual environment (recommended)

## Installation

1. **Clone the repository**:

   ```bash
   git clone <your-repo-url>
   cd FastAPI\Security\OAuth2
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install fastapi uvicorn psycopg2-binary python-dotenv passlib[bcrypt] pyjwt
   ```

4. **Set up environment variables**:

   - Create a `.env` file in the project root with the following content:

     ```
     DB_HOST=localhost
     DB_PORT=5432
     DB_NAME=fastapi_auth
     DB_USER=postgres
     DB_PASSWORD=your_password
     SECRET_KEY=your_secret_key
     ```
   - Replace `your_password` and `your_secret_key` with secure values.

5. **Set up the database**:

   - Connect to PostgreSQL:

     ```bash
     "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres
     ```
   - Create the database:

     ```sql
     CREATE DATABASE fastapi_auth;
     ```
   - Create required tables:

     ```sql
     CREATE TABLE users (
         username VARCHAR(50) PRIMARY KEY,
         hashed_password VARCHAR(255) NOT NULL
     );
     
     CREATE TABLE refresh_tokens (
         username VARCHAR(50) NOT NULL,
         refresh_token VARCHAR(255) NOT NULL,
         expiry TIMESTAMP NOT NULL,
         PRIMARY KEY (username, refresh_token),
         FOREIGN KEY (username) REFERENCES users(username)
     );
     
     CREATE TABLE products (
         id SERIAL PRIMARY KEY,
         name VARCHAR(100) NOT NULL,
         price DECIMAL(10, 2) NOT NULL,
         owner_username VARCHAR(50) NOT NULL,
         FOREIGN KEY (owner_username) REFERENCES users(username)
     );
     ```

## Running the Application

1. **Activate the virtual environment**:

   ```bash
   .venv\Scripts\activate
   ```

2. **Run the server**:

   ```bash
   uvicorn main:app --reload
   ```

   - The API will be available at `http://127.0.0.1:8000`.

3. **Access the API documentation**:

   - Open `http://127.0.0.1:8000/docs` in your browser to use Swagger UI.

## Usage

### Endpoints

- `/register` **(POST)**:

  - Register a new user.
  - Body: `{"username": "string", "password": "string"}`
  - Response: `{"access_token": "string", "refresh_token": "string", "token_type": "bearer"}`

- `/token` **(POST)**:

  - Log in to get tokens.
  - Body: Form data with `username` and `password`.
  - Response: `{"access_token": "string", "refresh_token": "string", "token_type": "bearer"}`

- `/refresh` **(POST)**:

  - Refresh an expired access token.
  - Body: `{"refresh_token": "string"}`
  - Response: `{"access_token": "string", "refresh_token": "string", "token_type": "bearer"}`

- `/products/` **(GET)**:

  - Get a list of products for the authenticated user.
  - Requires `Authorization: Bearer <token>` header.
  - Response: `[{"id": int, "name": "string", "price": float, "owner_username": "string"}]`

- `/products/` **(POST)**:

  - Create a new product.
  - Body: `{"name": "string", "price": float}`
  - Requires `Authorization: Bearer <token>` header.
  - Response: `{"id": int, "name": "string", "price": float, "owner_username": "string"}`

- `/protected` **(GET)**:

  - A sample protected route.
  - Requires `Authorization: Bearer <token>` header.
  - Response: `{"message": "Привет, <username>! Это защищенная зона"}`

### Example Workflow

1. Register a user:

   - Send `POST /register` with `{"username": "alice", "password": "password123"}`.
   - Receive tokens.

2. Log in:

   - Send `POST /token` with `username: alice`, `password: password123`.
   - Use the returned `access_token`.

3. Access protected routes:

   - Add `Authorization: Bearer <access_token>` to the header and call `/products/`.

## Contributing

Feel free to submit issues or pull requests. Suggestions for improvements are welcome!
=======

>>>>>>> 65af177d370b5b738f2884100adabc913c48d2cb
