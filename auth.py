# auth.py
from datetime import datetime, timedelta
import os
import asyncpg
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database import get_pool # Импортируем нашу зависимость для пула БД


# --- 1. Настройки и константы ---

# Загружаем переменные из .env, предоставляя значения по умолчанию для безопасности
SECRET_KEY = os.getenv('SECRET_KEY', 'a_very_secret_key_for_local_development')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Создаем объекты один раз при загрузке модуля
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token") # Указываем путь к эндпоинту для получения токена


# --- 2. Утилиты для работы с паролями ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, соответствует ли обычный пароль хешированному."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Хеширует пароль."""
    return pwd_context.hash(password)

# --- 3. Функции для создания токенов ---
# ИСПРАВЛЕНО: Эта функция теперь синхронная, так как создание токенов - быстрая операция.
# Она больше не лезет в БД и использует datetime-объекты напрямую, что решает ошибку "Signature has expired".
def create_tokens(data: dict) -> dict:
    """Создает новую пару access и refresh токенов."""
    
    # Создаем access token
    to_encode_access = data.copy()
    expire_access = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode_access.update({"exp": expire_access, "type": "access"})
    access_token = jwt.encode(to_encode_access, SECRET_KEY, algorithm=ALGORITHM)

    # Создаем refresh token
    to_encode_refresh = data.copy()
    expire_refresh = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode_refresh.update({"exp": expire_refresh, "type": "refresh"})
    refresh_token = jwt.encode(to_encode_refresh, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


# --- НОВАЯ ФУНКЦИЯ-ПОМОЩНИК ---
async def get_user_from_db(pool: asyncpg.Pool, username: str) -> dict | None:
    # --- НОВАЯ ФУНКЦИЯ-ПОМОЩНИК ---
    async with pool.acquire() as conn:
        user = await conn.fetchrow('SELECT username, hashed_password FROM users WHERE username = $1 ', username)
    return dict(user) if user else None


# --- 4. Зависимость для получения текущего пользователя ---
# ИСПРАВЛЕНО: Это теперь единственная и простая зависимость для проверки пользователя.
# Она напрямую запрашивает у FastAPI токен и пул соединений с БД.
async def get_current_user(
    token: str = Depends(oauth2_scheme), pool: asyncpg.Pool = Depends(get_pool)) -> dict:
    # Декодирует токен, проверяет его валидность и возвращает данные пользователя из БД.
    # Используется как зависимость в защищенных эндпоинтах.
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Проверяем, что это именно access токен
        if payload.get("type") != "access":
            raise credentials_exception
        
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        # Получаем пользователя из БД, чтобы убедиться, что он все еще существует
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT username, hashed_password FROM users WHERE username = $1", username)
        
        if user is None:
            raise credentials_exception
            
        # Возвращаем пользователя в виде словаря
        return dict(user)
    except JWTError:
        # Эта ошибка возникает, если токен просрочен или подпись неверна
        raise credentials_exception
