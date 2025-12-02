import os
from fastapi import FastAPI
from contextlib import asynccontextmanager


# --- 1. Импортируем наши модули ---
# ВАЖНО: config должен импортироваться до модулей, которые его используют.
# Он сам загрузит нужный .env или .env.test файл.
import config
# Импортируем функции для управления жизненным циклом БД
from database import connect_to_db, close_db_connection
# Импортируем готовые "удлинители" (роутеры) из каждого модуля
from auth import router as auth_router
# Добавляем импорт для роутера продуктов
from routers.products import router as products_router


# --- 2. Управление жизненным циклом приложения ---

# Это как "выключатель" для приложения, нужен для правильного включения и выключения подключения к БД
# # ИСПРАВЛЕНО: Используем новый, рекомендуемый способ управления жизненным циклом - lifespan.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления событиями "startup" и "shutdown".
    Это современный и надежный способ управлять ресурсами, такими как пул соединений с БД.
    """
    print("Lifespan starting")
    
    # # --- Начало: Код до yield ---
    # # Выполняется ОДИН РАЗ при старте сервера
    app.state.pool = None
    # Подключаемся, если TESTING не равен 'True'
    if os.getenv("TESTING") != "True":
        print("Connecting to database...")
        await connect_to_db(app)
    else:
        print("TESTING mode: skipping DB connect")

    # --- Основная работа ---
    yield # Приложение "живет" и обрабатывает запросы

    # --- Завершение: Код после yield ---
    # Выполняется ОДИН РАЗ при остановке сервера
    print("Lifespan shutting down")
    if os.getenv("TESTING") != True and app.state.pool:
        await close_db_connection(app)


# --- 3. Создаем и настраиваем приложение ---

# Создаем главный экземпляр FastAPI и передаем ему наш lifespan
app = FastAPI(
    title='My Refactored FastAPI App',
    description="Это приложение демонстрирует модульную архитектуру с аутентификацией, WebSocket и фоновыми задачами.",
    version='2.0.0',
    lifespan=lifespan 
)


# --- 4. Подключаем роутеры ---
# Используем app.include_router(), чтобы подключить все эндпоинты из наших модулей.
# FastAPI автоматически обработает префиксы (например, /auth, /compute), которые мы задали в каждом роутере.

# 1. Сначала импортируем роутеры (всегда)
from websocket import router as websocket_router
# Подключаем только необходимые роутеры для тестов
# bg_tasks пока можно оставить под условием, если не нужно их тестировать
if os.getenv('TESTING') != 'True':
    from bg_tasks import router as tasks_router
    app.include_router(tasks_router)

# 2. Подключаем основные роутеры (ВСЕГДА)
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(websocket_router)


# --- 5. Корневой эндпоинт (опционально) ---
# Это простой эндпоинт, чтобы можно было легко проверить, что сервер запущен.
@app.get('/', tags=['Root'])
def read_root():
    """Простой эндпоинт для проверки статуса API."""
    return {'status': 'API is running'}