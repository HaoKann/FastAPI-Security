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
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """
#     Контекстный менеджер для управления событиями "startup" и "shutdown".
#     Это современный и надежный способ управлять ресурсами, такими как пул соединений с БД.
#     """
#     print("Lifespan starting")
#     app.state.pool = None
#     # # --- Начало: Код до yield ---
#     # # Выполняется ОДИН РАЗ при старте сервера
#     # await connect_to_db(app)

#     # --- Основная работа ---
#     yield # Приложение "живет" и обрабатывает запросы
#     print("Lifespan shutting down")
#      # --- Завершение: Код после yield ---
#     # Выполняется ОДИН РАЗ при остановке сервера
#     # if app.state.pool:
#     #     await close_db_connection(app)


# --- 3. Создаем и настраиваем приложение ---

# Создаем главный экземпляр FastAPI и передаем ему наш lifespan
app = FastAPI(
    title='My Refactored FastAPI App',
    description="Это приложение демонстрирует модульную архитектуру с аутентификацией, WebSocket и фоновыми задачами.",
    version='2.0.0',
    # lifespan=lifespan # <--- Подключаем наш менеджер жизненного цикла
)


# --- 4. Подключаем роутеры ---
# Используем app.include_router(), чтобы подключить все эндпоинты из наших модулей.
# FastAPI автоматически обработает префиксы (например, /auth, /compute), которые мы задали в каждом роутере.

# Подключаем только необходимые роутеры для тестов
if os.getenv('TESTING') != 'True':
    from bg_tasks import router as tasks_router
    from websocket import router as websocket_router
    app.include_router(tasks_router)
    app.include_router(websocket_router)

app.include_router(auth_router)
app.include_router(products_router)


# --- 5. Корневой эндпоинт (опционально) ---
# Это простой эндпоинт, чтобы можно было легко проверить, что сервер запущен.
@app.get('/', tags=['Root'])
def read_root():
    """Простой эндпоинт для проверки статуса API."""
    return {'status': 'API is running'}