# Управление соединением с базой данных.
import asyncio
import asyncpg
from fastapi import Request
from config import settings


# Эта функция будет вызываться один раз при старте приложения
async def connect_to_db(app):
    # Создает пул соединений и сохраняет его для хранения общих ресурсов
    print('Connecting to database...')
    MAX_RETRIES = 5
    WAIT_SECONDS = 5


    # --- СБОРКА URL ---
    # asyncpg нужен "чистый" URL (postgresql://), а не как для SQLAlchemy (postgresql+asyncpg://)
    if settings.DATABASE_URL:
        # Если есть готовая ссылка (например, с Render), берем её
        db_url = settings.DATABASE_URL
    else:
        # Собираем вручную из настроек
        db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    # ------------------

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Используем db_url, который собрали выше (скрываем пароль в логах для безопасности)
            safe_url = db_url.split('@')[-1]
            print(f"DEBUG: Попытка подключения {attempt}/{MAX_RETRIES} к: {safe_url}")

            # 1. Создаем пул
            # app.state - специальный объект для хранения общих ресурсов
            # Используем DATABASE_URL, который уже содержит все данные
            app.state.pool = await asyncpg.create_pool(
                dsn=db_url,
                min_size=1, 
                max_size=20
            )
            print('✅ Database connection pool created successfully')



            # Если успешно - выходим из функции
            return 
        
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"Waiting {WAIT_SECONDS} seconds before retrying...")
                # ВАЖНО: await asyncio.sleep - это "умный" сон. 
                # Он не замораживает весь сервер, а просто ставит эту задачу на паузу.
                await asyncio.sleep(WAIT_SECONDS)
            else:
                print("Could not connect to DB after multiple attempts")
                raise e # Если все попытки исчерпаны - падаем
            


# Эта функция будет вызываться 1 раз при остановке приложения
async def close_db_connection(app):
    # Закрывает пул соединений при остановке приложений
    print('Closing database connection pool...')
    await app.state.pool.close()
    print('Database connection pool closed')

# Это зависимость (Dependency)
# Любой эндпоинт сможет запросить её для получания доступа к пулу
def get_pool(request: Request) -> asyncpg.Pool:
    # Зависимость для получения пула соединений в эндпоинтах.
    # FastAPI автоматически передаст сюда объект 'request', из которого можно получить доступ к app.state.pool
    return request.app.state.pool




