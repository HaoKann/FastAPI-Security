from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import settings


# Собираем URL для SQLAlchemy
SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

# Создаем асинхронный движок, управляет подключением под капотом
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# Создаем фабрику сессий для генерации новых сессий для каждого запроса к API
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Функция-зависимость для FastAPI
async def get_db_session():
    """Выдает одну сессию БД для конкретного запроса и закрывает её после"""
    async with async_session_maker() as session:
        yield session