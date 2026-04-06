# 🚀 FastAPI E-Commerce API (Clean Architecture)

![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-316192.svg)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg)
![Coverage](https://img.shields.io/badge/coverage-70%25-brightgreen.svg)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF.svg)

---

## 📌 About the Project

This is a backend API for an e-commerce platform where users can:

* Register and authenticate
* Create and manage products
* Upload avatars
* Browse products with pagination

---

## ✨ Features

* **Clean Architecture**: Clear separation of concerns (`Routers` → `Services` → `Repositories`).
* **Advanced Authentication**: OAuth2 with JWT (Access & Refresh tokens).
* **Strict Validation**: Using **Pydantic v2** (`Annotated`, `computed_field`, custom validators).
* **High Performance**: Redis caching for faster responses.
* **Frontend SPA**: Vanilla JS client with pagination and error handling.
* **Dockerized**: Easy setup using Docker Compose.
* **CI/CD Ready**: GitHub Actions pipeline.
* **Cloud Storage**: S3 (Backblaze B2) integration for avatars.

---

## 🛠️ Tech Stack

* **Backend**: FastAPI, Uvicorn, Python 3.13
* **Database**: PostgreSQL (`asyncpg`)
* **Cache**: Redis
* **Security**: Passlib (Bcrypt), PyJWT
* **Testing**: Pytest, Pytest-Asyncio, Pytest-Cov
* **Deployment**: Docker, Render

---

## 🚀 Quick Start (Docker)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd FastAPI-Security-OAuth2
```

### 2. Create `.env` file

```env
DATABASE_URL=postgresql://user:password@db:5432/fastapi_db
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your_super_secret_jwt_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 3. Build and run

```bash
docker-compose up --build
```

### 4. Access the app

* Web Client: [http://localhost:8000](http://localhost:8000)
* Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 💻 Manual Setup

### 1. Create virtual environment

```bash
python -m venv .venv
```

```bash
# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create database tables

```sql
CREATE TABLE users (
    username VARCHAR(50) PRIMARY KEY,
    hashed_password VARCHAR(255) NOT NULL,
    avatar_url VARCHAR(255)
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    owner_username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE
);
```

### 4. Run server

```bash
uvicorn main:app --reload
```

---

## 🧪 Testing

Run tests:

```bash
pytest
```

Generate coverage report:

```bash
pytest --cov=. --cov-report=term-missing
```

---

## 📂 Project Structure

```
├── main.py                 # Entry point
├── database.py             # DB & dependencies
├── routers/                # API endpoints
├── services/               # Business logic
├── repositories/           # Data access layer
├── tests/                  # Tests
├── docker-compose.yml
└── ...
```

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

Make sure all tests pass before submitting a PR.
