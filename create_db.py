import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from models import Base

# Загружаем пароль из .env файла
load_dotenv()
password = os.getenv("DB_PASSWORD")

# Подключаемся к базе через порт 5433 (который мы пробросили из Докера)
DATABASE_URL = f"postgresql+asyncpg://postgres:{password}@localhost:5433/fastapi_auth"

engine = create_async_engine(DATABASE_URL, echo=True)

async def init_models():
    async with engine.begin() as conn:
        print("Очищаем базу (если что-то осталось)...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Создаем свежие таблицы из models.py...")
        await conn.run_sync(Base.metadata.create_all)
    print("Готово! Идеально чистая база создана.")

if __name__ == "__main__":
    asyncio.run(init_models())