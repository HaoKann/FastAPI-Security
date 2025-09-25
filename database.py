# Управление соединением с базой данных.

import os
import asyncpg
from fastapi import Request

# Импортируем готовые настройки из нашего центрального конфига
from config import DATABASE_URL, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

# Эта функция будет вызываться один раз при старте приложения
async def connect_to_db(app):
    # Создает пул соединений и сохраняет его для хранения общих ресурсов
    # app.state - специальный объект для хранения общих ресурсов
    print('Connecting to database...')
    # Используем DATABASE_URL, который уже содержит все данные
    app.state.pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
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




