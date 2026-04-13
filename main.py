# --- 1. Импортируем наши модули ---
import os
import time
from redis import asyncio as aioredis
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import sentry_sdk
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

# --- 2. Управление жизненным циклом приложения ---
# Это как "выключатель" для приложения, нужен для правильного включения и выключения подключения к БД
# # ИСПРАВЛЕНО: Используем новый, рекомендуемый способ управления жизненным циклом - lifespan.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления событиями "startup" и "shutdown".
    Это современный и надежный способ управлять ресурсами, такими как пул соединений с БД.
    """

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

