# conftest.py
import os
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from starlette import status

# Устанавливаем переменную окружения ДО импорта приложения
os.environ['TESTING'] = 'True'
print('Starting app import...')

try:
    from main import app
    print('App imported successfully')
except Exception as e:
    print(f"Error importing app: {e}")
    raise

from create_db import get_db_session
from models import Base, User # Импортируем Base, чтобы Алхимия знала, какие таблицы создавать
from websocket import manager

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

# --- 1. Настройка тестовой БД (в оперативной памяти) ---
# Используем SQLite в памяти: работает молниеносно, данные стираются после остановки
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}, # Нужно для работы SQLite
    poolclass=StaticPool, # Гарантирует, что соединение не закроется посреди теста
    echo=False
)

TestingSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


# --- 2. Фикстуры ---

@pytest.fixture(scope="function")
async def db_session():
    """
    Создает чистую базу данных для каждого теста.
    """
    # 1. Создаем все таблицы перед тестом
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Выдаем сессию тесту
    async with TestingSessionLocal() as session:
        yield session
        
    # 3. Удаляем все таблицы после завершения теста (убираем за собой)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope='function')
def client(db_session):
    """
    Виртуальный Postman с подмененной базой данных.
    """
    print('Creating TestClient')
    
    # Создаем функцию, которая всегда возвращает нашу тестовую сессию
    def override_get_db():
        yield db_session

    # Говорим FastAPI использовать нашу тестовую сессию вместо боевой
    app.dependency_overrides[get_db_session] = override_get_db
    
    # Очищаем соединения вебсокетов перед тестом
    manager.active_connections = {}

    with TestClient(app, raise_server_exceptions=False) as test_client:
        print('TestClient created')
        yield test_client
        print('TestClient closed')
        
    # Возвращаем всё как было после теста
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers(client: TestClient):
    """
    Регистрирует тестового юзера, логинит его и возвращает заголовки с токеном.
    Благодаря реальной тестовой БД в памяти, это работает по-настоящему!
    """
    # Шаг 1: Регистрируем пользователя
    user_data = {
        "username": "test_user",
        "password": "strongpassword123" 
    }
    response_register = client.post('/auth/register', json=user_data)
    assert response_register.status_code == status.HTTP_200_OK

    # Шаг 2: Логинимся
    login_data = {
        "username": "test_user",
        "password": "strongpassword123"
    }
    response_login = client.post('/auth/login', data=login_data)
    assert response_login.status_code == status.HTTP_200_OK

    # Шаг 3: Вытаскиваем токен
    token_data = response_login.json()
    access_token = token_data["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    yield headers


@pytest.fixture(scope="function")
async def ac(db_session):
    """
    Асинхронный клиент (AsyncClient) для тестов.
    """
    # Также подменяем базу для асинхронного клиента
    def override_get_db():
        yield db_session
        
    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
        
    app.dependency_overrides.clear()