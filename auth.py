# auth.py
from datetime import datetime, timedelta, UTC
import os
import asyncpg
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from database import get_pool # Импортируем нашу зависимость для пула БД
from pydantic import BaseModel


# --- 1. Настройки и объекты ---
# Загружаем переменные из .env, предоставляя значения по умолчанию для безопасности
SECRET_KEY = os.getenv('SECRET_KEY', 'a_very_secret_key_for_local_development')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Создаем объекты один раз при загрузке модуля
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# ИСПРАВЛЕНО: Создаем простой security-объект. Он создаст правильную кнопку "Authorize".
security = HTTPBearer()

# СОЗДАЕМ ROUTER: Это наш "удлинитель" для всех эндпоинтов аутентификации
router = APIRouter(
    prefix='/auth', # Все пути в этом файле будут начинаться с /auth
    tags=['Authentication'] # Группировка в документации Swagger
)

# --- 2. Модели Pydantic ---
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    username: str

# --- 3. Утилиты (без изменений) ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, соответствует ли обычный пароль хешированному."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Хеширует пароль."""
    return pwd_context.hash(password)

# --- Функции для создания токенов ---
# ИСПРАВЛЕНО: Эта функция теперь синхронная, так как создание токенов - быстрая операция.
# Она больше не лезет в БД и использует datetime-объекты напрямую, что решает ошибку "Signature has expired".
def create_tokens(data: dict) -> dict:
    """Создает новую пару access и refresh токенов."""
    
    # Создаем access token
    to_encode_access = data.copy()
    expire_access = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode_access.update({"exp": expire_access, "type": "access"})
    access_token = jwt.encode(to_encode_access, SECRET_KEY, algorithm=ALGORITHM)

    # Создаем refresh token
    to_encode_refresh = data.copy()
    expire_refresh = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode_refresh.update({"exp": expire_refresh, "type": "refresh"})
    refresh_token = jwt.encode(to_encode_refresh, SECRET_KEY, algorithm=ALGORITHM)
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

# --- НОВАЯ ФУНКЦИЯ-ПОМОЩНИК ---
async def get_user_from_db(pool: asyncpg.Pool, username: str) -> dict | None:
    print("Тип объекта pool:", type(pool))
    async with pool.acquire() as conn:
        user = await conn.fetchrow('SELECT username, hashed_password FROM users WHERE username = $1 ', username)
    return dict(user) if user else None


# --- 4. Зависимость для получения текущего пользователя ---
# Она напрямую запрашивает у FastAPI токен и пул соединений с БД.
# ИСПРАВЛЕНО: Функция теперь зависит от HTTPBearer
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    # Декодирует токен, проверяет его валидность и возвращает данные пользователя из БД.
    # Используется как зависимость в защищенных эндпоинтах.
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    token = credentials.credentials # Извлекаем токен из объекта credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Проверяем, что это именно access токен
        if payload.get("type") != "access":
            raise credentials_exception
        username = payload.get('sub')
        if username is None:
            raise credentials_exception
        return {'username': username}
    except JWTError:
        raise credentials_exception


# --- 5. НОВЫЙ БЛОК: Эндпоинты, перенесенные из main.py ---

# Эндпоинт для регистрации
# Принимает данные пользователя, проверяет, не существует ли такой username, хэширует пароль и сохраняет в users. 
# Затем выдаёт токены.
@router.post('/register', response_model=Token)
# user: UserCreate — объект, созданный из JSON-запроса (например, {"username": "alice", "password": "password123"}).
async def register(user_in: UserCreate, pool: asyncpg.Pool = Depends(get_pool)):
    try:
        # Асинхронно проверяет наличие пользователя.
        if await get_user_from_db(pool, user_in.username):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Пользователь с таким именем уже существует')
        
        hashed_password = get_password_hash(user_in.password)
    # Использует асинхронное соединение для записи.
        async with pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO users (username, hashed_password) VALUES ($1, $2)',
                user_in.username, hashed_password
            )
        return create_tokens(data={'sub': user_in.username})
    except Exception as e:
        print('Ошибка в register', e)
        raise


# Эндпоинт для получения токена
@router.post("/login", response_model=Token)
async def login_for_token(form_data: OAuth2PasswordRequestForm = Depends(), pool: asyncpg.Pool = Depends(get_pool)):
    """Выдает access и refresh токены для пользователя."""
    user = await get_user_from_db(pool, form_data.username)

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={'WWW-Authenticate': 'Bearer'},
        )
    
    return create_tokens(data={"sub": user["username"]})

@router.get('/me', summary='Get current user info', response_model=UserOut)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user # Pydantic автоматически отфильтрует нужные поля


# Защищенный эндпоинт для пользователя
@router.get('/protected')
async def protected_route(current_user: dict = Depends(get_current_user)):
    # Мы ожидаем словарь (dict) и берем из него имя пользователя
    username = current_user['username']
    return {'message': f'Привет, {username}! Это защищенная зона'}