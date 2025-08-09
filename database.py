# Управление соединением с базой данных.

import asyncpg
from fastapi import Request
import os

# Эта функция будет вызываться один раз при старте приложения
async def connect_to_db(app):
    # Создает пул соединений и сохраняет его для хранения общих ресурсов
    # app.state - специальный объект для хранения общих ресурсов
    print('Connecting to database...')
    app.state.pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME', 'fastapi_auth'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '123456789'),
        min_size=1,
        max_size=20
    )
    print('Database connection pool created successfully')

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




