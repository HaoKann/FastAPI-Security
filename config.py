import os
import sys # <-- Добавляем импорт для системных утилит
from dotenv import load_dotenv
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- 1. Настройки БД (компоненты) ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "fastapi_auth"

    # Ссылка целиком (для продакшена/Render)
    DATABASE_URL: Optional[str] = None 
    
    # --- 2. Настройки безопасности ---
    SECRET_KEY: str
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- 3. Настройки Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"


    # --- 4. Настройки S3 (MinIO) - НОВЫЕ ПОЛЯ ---
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_ENDPOINT_URL: str
    S3_BUCKET_NAME: str

    # Логика загрузки .env файла
    model_config = SettingsConfigDict(
        # Умный выбор файла:
        env_file=".env.test" if "pytest" in sys.modules else ".env",
        env_file_encoding="utf-8",
        extra="ignore" # Игнорировать лишние переменные в .env
    )

    @property
    def get_database_url(self) -> str:
        """
        Собирает URL базы данных. 
        Приоритет: 
        1. DATABASE_URL из .env (если есть)
        2. Сборка из отдельных полей (DB_HOST, etc...)
        """
        url = self.DATABASE_URL

        # Если ссылки нет, собираем её сами
        if not url:
            url = f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

        # Хак для Render (замена postgres:// на postgresql://)
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)

        # Убедимся, что драйвер asyncpg (если его нет в строке)
        if url and not url.startswith('postgresql+asyncpg://') and url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)

        return url
    
# Создаем экземпляр настроек, который будем импортировать
settings = Settings()
