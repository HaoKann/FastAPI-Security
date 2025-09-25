import os
import sys # <-- Добавляем импорт для системных утилит
from dotenv import load_dotenv


# --- ИСПРАВЛЕНИЕ: "Умная" загрузка конфигурации ---
# Проверяем, был ли запущен Python через Pytest
if "pytest" in sys.modules:
    # Если да, загружаем переменные из .env.test
    print("--- PYTEST DETECTED: Загружается конфигурация из .env.test")
    load_dotenv(".env.test")
else:
    # В обычном режиме (через uvicorn) загружаем из .env
    print("--- PRODUCTION MODE: Загружается конфигурация из .env ---")
    load_dotenv()

# --- Собираем все настройки в одном месте ---

# Настройки JWT
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Настройки подключения к БД
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Полный "адрес" для asyncpg
DATABASE_URL = (
    f"postgres://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Настройки Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0d')