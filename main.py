# --- 1. Импортируем наши модули ---
import os
import time
from redis import asyncio as aioredis
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from config import settings

# ВАЖНО: config должен импортироваться до модулей, которые его используют.
# Он сам загрузит нужный .env или .env.test файл.

# Импортируем функции для управления жизненным циклом БД
from database import connect_to_db, close_db_connection

# Импортируем готовые "удлинители" (роутеры) из каждого модуля
from auth import router as auth_router

# Добавляем импорт для роутера продуктов
from routers.products import router as products_router

# Frontend
from fastapi.staticfiles import StaticFiles # <-- Импорт для папки
from fastapi.responses import FileResponse # <-- Импорт для отдачи файла

# GraphQL
from strawberry.fastapi import GraphQLRouter
from graphql_app.schema import schema # Импортируем нашу схему

# S3
from routers import media, users

from websocket import router as websocket_router

# Safety
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter


# Observability 
import sentry_sdk
from prometheus_fastapi_instrumentator import Instrumentator


import json
import asyncio
from websocket import manager

# Logging
# import logging
# from pythonjsonlogger import jsonlogger

# # Настраиваем формат логов
# logHandler = logging.StreamHandler()
# formatter = jsonlogger.JsonFormatter(
#     '%(timestamp)s %(level)s %(name)s %(message)s',
#     timestamp = True
# )
# logHandler.setFormatter(formatter)

# # Применяем настройки к основному логгеру
# logger = logging.getLogger()
# logger.addHandler(logHandler)
# logger.setLevel(logging.INFO)

# # Убираем стандартные обработчики, чтобы не было дублей
# logger.propagate = False


async def listen_to_redis():
    """Фоновая задача FastAPI для прослушивания канала Redis"""
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        redis_client = await aioredis.from_url(redis_url)

        pubsub = redis_client.pubsub()
        await pubsub.subscribe('celery_notifications')

        print("🎧 FastAPI начал слушать канал celery_notifications...")

        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                target_username = data.get('username')
                text = data.get('message')

                print(f"📩 Получено из Redis для {target_username}: {text}")
                await manager.send_personal_message(text, target_username)
    except Exception as e:
        print(f"❌ Ошибка прослушивания Redis: {e}")

# --- 2. Управление жизненным циклом приложения ---
# Это как "выключатель" для приложения, нужен для правильного включения и выключения подключения к БД
# # ИСПРАВЛЕНО: Используем новый, рекомендуемый способ управления жизненным циклом - lifespan.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления событиями "startup" и "shutdown".
    Это современный и надежный способ управлять ресурсами, такими как пул соединений с БД.
    """

    # ИСПРАВЛЕНО: Сохраняем жесткую ссылку на задачу, чтобы Питон ее не убил!
    # Запускаем и "якорим" слушателя ТОЛЬКО для реальной работы, отключаем для тестов
    if os.getenv('TESTING') != 'True':
        app.state.redis_task = asyncio.create_task(listen_to_redis())

    # Инициализируем переменные, чтобы они существовали в любом случае
    app.state.pool = None
    app.state.redis = None

    # # --- Начало: Код до yield ---
    # # Выполняется ОДИН РАЗ при старте сервера
    # Подключаемся, если TESTING не равен 'True'
    if os.getenv("TESTING") != "True":
        print("Connecting to services...")

        # 1. Подключение к Postgres
        await connect_to_db(app)

        # 2. Подключение к Redis
        try:
            print("Connect to Redis...")
            # 'fastapi_redis' — это имя сервиса из docker-compose.yml
            # decode_responses=True — чтобы получать строки, а не байты
            redis = aioredis.from_url('redis://fastapi_redis:6379', encoding='utf8', decode_responses=True)
            app.state.redis = redis

            # Инициализируем защиту от спама
            await FastAPILimiter.init(redis)
            print("✅ Rate Limiter initialized")

            print("✅ Redis connected successfully")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")


        print("\n" + "="*50)
        print("🚀  SERVER IS READY!")
        print("👉  Open Swagger UI: http://localhost:8001")
        print("="*50 + "\n")
    else:
        print("TESTING mode: skipping DB connect and Redis connect")

    # --- Основная работа ---
    yield # Приложение "живет" и обрабатывает запросы

    # --- Завершение: Код после yield ---
    # Выполняется ОДИН РАЗ при остановке сервера
    print("Lifespan shutting down")

    # 1. Закрываем Postgres
    if app.state.pool:
        await close_db_connection(app)

    # 2. Закрываем Redis
    if app.state.redis:
        print('Closing Redis connection...')
        await app.state.redis.close()


# --- ИНИЦИАЛИЗАЦИЯ SENTRY ---
# Запускаем Sentry до создания самого приложения FastAPI
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0
    )
    print("✅ Sentry is tracking errors!")

# --- 3. Создаем и настраиваем приложение ---
# Создаем главный экземпляр FastAPI и передаем ему наш lifespan
app = FastAPI(
    title='My Refactored FastAPI App',
    description="Это приложение демонстрирует модульную архитектуру с аутентификацией, WebSocket и фоновыми задачами.",
    version='2.0.0',
    lifespan=lifespan 
)

# Инициализация мониторинга (Prometheus)
Instrumentator().instrument(app).expose(app)

# Разрешенные источники (домены фронтенда)
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8001",
    "http://127.0.0.1:8000",
]


app.add_middleware(
    CORSMiddleware,
    # allow_origins=origins # Для продакшена нужно раскомментировать эту строку!
    allow_origins=["*"], # Для локальных тестов пока разрешаем всем ("*")
    allow_credentials=True,
    allow_methods=["*"], # Разрешаем все методы (GET, POST, PUT, DELETE)
    allow_headers=["*"], # Разрешаем все заголовки
)


@app.middleware('http')
async def add_process_time_header(request: Request, call_next):
    # 1. Засекаем время ДО начала обработки
    start_time = time.time()

    # 2. Передаем запрос дальше (в другие middleware и в твою ручку)
    response = await call_next(request)

    # 3. Замеряем время ПОСЛЕ
    process_time = time.time() - start_time

    # 4. Добавляем заголовок в ответ (время в секундах)
    response.headers['X-Process-Time'] = str(process_time)

    return response


# Подключаем папку static, чтобы браузер мог брать оттуда script.js и стили
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- ПОДКЛЮЧАЕМ GRAPHQL ---
# Создаем роутер, передавая ему схему
graphql_app = GraphQLRouter(schema)

# Подключаем его к приложению
# prefix="/graphql" означает, что он будет доступен по адресу http://сайт/graphql
app.include_router(graphql_app, prefix='/graphql')




# --- 4. Подключаем роутеры ---
# Используем app.include_router(), чтобы подключить все эндпоинты из наших модулей.
# FastAPI автоматически обработает префиксы (например, /auth, /compute), которые мы задали в каждом роутере.

# 1. Сначала импортируем роутеры (всегда)

# Подключаем только необходимые роутеры для тестов
# bg_tasks пока можно оставить под условием, если не нужно их тестировать
if os.getenv('TESTING') != 'True':
    from bg_tasks import router as tasks_router
    app.include_router(tasks_router)

# 2. Подключаем основные роутеры (ВСЕГДА)
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(websocket_router)
app.include_router(media.router)
app.include_router(users.router)


# --- 5. Корневой эндпоинт (опционально) ---
# Изменяем главный маршрут: теперь он отдает HTML-файл, а не редирект
@app.get('/')
async def root():
    return FileResponse('static/index.html')

