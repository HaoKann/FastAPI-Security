import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from models import Base
from config import settings

# Загружаем пароль из .env файла
load_dotenv()
password = os.getenv("DB_PASSWORD")

# Собираем URL для SQLAlchemy
SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

# Создаем асинхронный движок, управляет подключением под капотом
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# Создаем фабрику сессий для генерации новых сессий для каждого запроса к API
async_sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Функция-зависимость для FastAPI
async def get_db_session():
    """Выдает одну сессию БД для конкретного запроса и закрывает её после"""
    async with async_sessionmaker() as session:
        yield session