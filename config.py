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
ALGORITHM = os.getenv('ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# --- Настройки подключения к БД ---
# Мы добавляем значения по умолчанию (None), чтобы код не падал сразу, 
# но если Docker не передаст переменную, мы это увидим при сборке URL.
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')


# --- Сборка URL для asyncpg ---
# ВАЖНО: Используем 'postgresql://', это стандарт.
DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Для отладки (потом можно убрать): выводим, куда пытаемся стучаться
# ВНИМАНИЕ: Это выведет пароль в логи, используй только при отладке!
print(f"DEBUG: Configured DATABASE_URL={DATABASE_URL}")

# Настройки Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')