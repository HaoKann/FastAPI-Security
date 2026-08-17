# auth.py
from datetime import datetime, timedelta, UTC
import os
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Optional
from s3_service import s3_client

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from create_db import get_db_session
from models import User

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
    password: str = Field(..., max_length=72)

class UserOut(BaseModel):
    username: str
    avatar_url: Optional[str] = None
    
    
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


# --- НОВАЯ ФУНКЦИЯ-ПОМОЩНИК НА SQLALCHEMY ---
async def get_user_from_db(db: AsyncSession, username: str) -> dict | None:
    """Получает пользователя из БД. Возвращает None в тестовом режиме."""
    print(f"get_user_from_db вызван, db={type(db)}, username={username}")

    # КРИТИЧЕСКИ ВАЖНО: Проверка на None для тестового режима
    if db is None:
        print("TESTING mode: returning None from get_user_from_db")
        return None

    # Делаем запрос через SQLAlchemy
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    # Чтобы не ломать старый код, отдаем данные в виде словаря
    if user:
        return {
            'username' : user.username,
            'hashed_password': user.hashed_password,
            'avatar_url': user.avatar_url,
            'role': user.role
        }
    return None


# --- 4. Зависимость для получения текущего пользователя ---
# Она напрямую запрашивает у FastAPI токен и пул соединений с БД.
# ИСПРАВЛЕНО: Функция теперь зависит от HTTPBearer
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session) #  1. Даем функции доступ к БД
) -> dict:
    
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentioals")

    token = credentials.credentials # Извлекаем токен из объекта credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Проверяем, что это именно access токен
        if payload.get("type") != "access":
            raise credentials_exception
        username = payload.get('sub')
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 👇 2. Идем в базу данных за ПОЛНЫМИ данными пользователя
    user = await get_user_from_db(db, username)
    if user is None:
        raise credentials_exception

    # Возвращаем полный словарь (там теперь есть username, hashed_password и avatar_url)
    return user


# --- 5. НОВЫЙ БЛОК: Эндпоинты, перенесенные из main.py ---

# Эндпоинт для регистрации
# Принимает данные пользователя, проверяет, не существует ли такой username, хэширует пароль и сохраняет в users. 
# Затем выдаёт токены.
@router.post('/register', response_model=Token)
# user_in: UserCreate — объект, созданный из JSON-запроса (например, {"username": "alice", "password": "password123"}).
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db_session)):
    try:
        # Асинхронно проверяет наличие пользователя.
        if await get_user_from_db(db, user_in.username):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Пользователь с таким именем уже существует')
        
        hashed_password = get_password_hash(user_in.password)

        # Создаем нового пользователя через SQLAlchemy
        new_user = User(username=user_in.username, hashed_password=hashed_password)
        db.add(new_user)
        await db.commit()
        
                
        return create_tokens(data={'sub': user_in.username})
    except Exception as e:
        print('Ошибка в register', e)
        raise


# Эндпоинт для получения токена
@router.post("/login", response_model=Token)
async def login_for_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db_session)):
    """Выдает access и refresh токены для пользователя."""
    user = await get_user_from_db(db, form_data.username)

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={'WWW-Authenticate': 'Bearer'},
        )
    
    return create_tokens(data={"sub": user["username"]})

@router.get('/me', summary='Get current user info', response_model=UserOut)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    # 1. Достаем имя файла аватарки из профиля пользователя
    avatar_filename = current_user.get('avatar_url')

    # 2. Если аватарка вообще существует (пользователь ее загружал)
    if avatar_filename:
        # Генерируем временную ссылку на 1 час через наш S3 сервис
        presigned_url = await s3_client.get_presigned_url(avatar_filename)

        # Подменяем короткое имя файла на длинную временную ссылку
        current_user['avatar_url'] = presigned_url
        
    # 3. Отдаем профиль фронтенду (Pydantic сам всё отфильтрует)
    return current_user 


# Защищенный эндпоинт для пользователя
@router.get('/protected')
async def protected_route(current_user: dict = Depends(get_current_user)):
    # Мы ожидаем словарь (dict) и берем из него имя пользователя
    username = current_user['username']
    return {'message': f'Привет, {username}! Это защищенная зона'}



# --- РОЛЕВАЯ МОДЕЛЬ (RBAC) ---
class RoleChecker:
    """Проверяет, есть ли у текущего пользователя нужная роль."""
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
        
    def __call__(self, current_user: dict = Depends(get_current_user)):
        user_role = current_user.get('role', 'user')
        
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для выполнения этого действия"
            )
        return current_user

# Создаем готовую зависимость для админов
require_admin = RoleChecker(['admin'])