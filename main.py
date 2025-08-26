from fastapi import FastAPI
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Загружаем переменные окружения в самом начале.
# Это важно сделать до импорта других модулей, которые их используют.
load_dotenv()


# --- 1. Импортируем наши модули ---

# Импортируем функции для управления жизненным циклом БД
from database import connect_to_db, close_db_connection
# Импортируем готовые "удлинители" (роутеры) из каждого модуля
from auth import router as auth_router
from bg_tasks import router as tasks_router
from websocket import router as websocket_router
# Добавляем импорт для роутера продуктов
from routers.products import router as products_router


# --- 2. Управление жизненным циклом приложения ---

# Это как "выключатель" для приложения, нужен для правильного включения и выключения подключения к БД
# ИСПРАВЛЕНО: Используем новый, рекомендуемый способ управления жизненным циклом - lifespan.
# Это решает ошибку "coroutine was never awaited" при старте.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Начало: Код до yield ---
    # Выполняется ОДИН РАЗ при старте сервера
    await connect_to_db(app)

    # --- Основная работа ---
    yield # Приложение "живет" и обрабатывает запросы

     # --- Завершение: Код после yield ---
    # Выполняется ОДИН РАЗ при остановке сервера
    await close_db_connection(app)

# --- 3. Создаем и настраиваем приложение ---


# Создаем главный экземпляр FastAPI и передаем ему наш lifespan
app = FastAPI(
    title='My Refactored FastAPI App',
    description="Это приложение демонстрирует модульную архитектуру с аутентификацией, WebSocket и фоновыми задачами.",
    version='1.0.0',
    lifespan=lifespan
)


# --- 4. Подключаем роутеры ---
# Используем app.include_router(), чтобы подключить все эндпоинты из наших модулей.
# FastAPI автоматически обработает префиксы (например, /auth, /compute), которые мы задали в каждом роутере.
app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(websocket_router)
app.include_router(products_router)


# --- 4. Корневой эндпоинт (опционально) ---
# Это простой эндпоинт, чтобы можно было легко проверить, что сервер запущен.
@app.get('/', tags=['Root'])
def read_root():
    """Простой эндпоинт для проверки статуса API."""
    return {'status': 'API is running'}