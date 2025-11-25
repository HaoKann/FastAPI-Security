# conftest.py — это глобальный файл конфигурации pytest.
# Любые фикстуры, объявленные здесь, доступны во всех тестах, без импортов.


import pytest
from fastapi.testclient import TestClient
import os
from starlette import status
from websocket import manager

# --- 1. Настройка тестового окружения ---

# Устанавливаем переменную окружения, чтобы приложение "знало",
# что оно запущено в режиме тестирования. Это позволит нам в будущем
# подменять, например, настоящую БД на тестовую.
os.environ['TESTING'] = 'True'
print('Starting app import...')
# ВАЖНО: Импортируем `app` из main.py ПОСЛЕ установки переменной окружения.
try:
    from main import app
    print('App imported successfully')
except Exception as e:
    print(f"Error importing app: {e}")
    raise



# --- 2. Создаем наши "помощники" (фикстуры) ---
# Фикстуры — это функции с декоратором @pytest.fixture.
# Они создают или подготавливают нужные объекты для тестов.

# Хранение имён зарегистрированных пользователей между вызовами mock-функций
existing_users = set() # пустое множество — пользователей ещё нет

# "таблица" продуктов
fake_products_db = []
# "счетчик" ID 
fake_product_id_counter = 1


# scope='function' — значит, фикстура выполняется перед каждым тестом заново и "сбрасывается" после него.
# (Можно также scope='session', чтобы создавать один раз на все тесты.)
@pytest.fixture(scope='function')
def db_pool(monkeypatch):
    global existing_users, fake_products_db, fake_product_id_counter
    existing_users.clear()  # очищаем перед каждым тестом
    fake_products_db.clear()
    fake_product_id_counter = 1
    manager.active_connections = []

    # mock_get_user_from_db, которая имитирует поведение реальной функции:
    async def mock_get_user_from_db(pool, username):
        # если пользователь уже существует, возвращает фейкового юзера, иначе None.
        if username in existing_users:
            return {'username': username, 'hashed_password': 'hashed_password'}
        return None
    
    # Эта "обманка" будет имитировать проверку пароля
    def mock_verify_password(plain_password, hashed_password):
        return hashed_password == "hashed_password" and plain_password == 'strongpassword123'

    # Вспомогательная функция для выполнения INSERT в "памяти"
    async def mock_insert_user(username):
        existing_users.add(username)
    

    # Фейковый пул и соединение
    # mock_get_pool() — это фейковая (тестовая) замена реального пула соединений с базой (asyncpg.Pool).
    def mock_get_pool():
        # MockConnection — имитирует одно соединение.
        class MockConnection:
            # имитирует conn.fetchrow(...)
            async def fetchrow(self, query, *args):
                global fake_product_id_counter

                if "INSERT INTO products" in query:
                    new_product = {
                        "id": fake_product_id_counter, "name": args[0],
                        "price": args[1], "owner_username": args[2]
                    }
                    fake_products_db.append(new_product)
                    fake_product_id_counter += 1
                    print(f"TESTING mode: Продукт '{new_product['name']}' добавлен в mock DB.")
                    return new_product
                # Логика для поиска пользователя
                if "SELECT" in query and "users" in query:
                    if args and args[0] in existing_users:
                        return {'username': args[0], 'hashed_password': 'hashed_password'}
                return None
            
            # имитирует conn.fetch(...)
            async def fetch(self, query, *args):
                if "SELECT" in query and "products" in query:
                   return [p for p in fake_products_db if p["owner_username"] == args[0]]
                return []
            
            # имитирует conn.execute(...)
            async def execute(self, query, *args):
                # Эмулируем INSERT INTO users (username, hashed_password) VALUES ($1, $2)
                if isinstance(query, str) and "INSERT INTO users" in query:
                    # Получаем доступ к "фейковой" БД
                    global existing_users
                    # Добавляем пользователя
                    existing_users.add(args[0])
                    print(f"!!! УСПЕХ: User '{args[0]}' добавлен в mock DB.")
                    return "OK"
                return "OK"
            
            # async def __aenter__ и async def __aexit__ — позволяют использовать объект в async with (контекстный менеджер)
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
            
        # MockPool — имитирует пул соединений:
        class MockPool:
            def acquire(self):
                return MockConnection()
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
        
        return MockPool()
    

    # ПРИМЕНЯЕМ ПОДМЕНЫ 
    # А. Подменяем функции внутри auth.py
    monkeypatch.setattr('auth.get_user_from_db', mock_get_user_from_db)
    try:
        # "Подменяем" настоящую функцию проверки пароля на нашу "обманку"
        monkeypatch.setattr('auth.verify_password', mock_verify_password)
    except AttributeError:
        monkeypatch.setattr('auth.verify_password', mock_verify_password)
    
    # Б. Подменяем ЗАВИСИМОСТЬ (Depends) во всем приложении
    # Это заменяет get_pool на mock_get_pool везде, где есть Depends(get_pool)
    from database import get_pool as original_get_pool
    from main import app

    app.dependency_overrides[original_get_pool] = mock_get_pool

    # Фикстура завершает работу
    yield # Используем yield, чтобы фикстура "жила", пока идет тест

    app.dependency_overrides = {}



# Эта фикстура создаёт TestClient — встроенный инструмент FastAPI, который:
# запускает приложение внутри Python-процесса (без uvicorn),
# позволяет делать HTTP-запросы (client.get(), client.post() и т.д.),
# возвращает ответы как Response объекты.
@pytest.fixture(scope='function')
def client(db_pool):
    """
    Эта фикстура создает "виртуальный Postman" (TestClient) для нашего приложения.
    Она будет выполняться один раз для каждого тестового файла.
    """
    print('Creating TestClient')
    # Контекстный менеджер `with` гарантирует, что все "включения" и "выключения"
    # нашего приложения (lifespan) будут корректно вызваны. 
    with TestClient(app, raise_server_exceptions=False) as test_client:
        # `yield` передает управление тесту, который запросил этого "помощника".
        print('TestClient created')
        yield test_client
        print('TestClient closed')



@pytest.fixture(scope="function")
def auth_headers(client: TestClient):
    """
    Фикстура-помощник:
    1. Создает стандартного 'test_user'.
    2. Логинится этим пользователем.
    3. Возвращает готовый 'headers' для запросов.
    """
    # --- Шаг 1: Регистрируем пользователя ---
    user_data = {
        "username": "test_user",
        "password": "strongpassword123" # Пароль, который "знает" наш mock_verify_password
    }
    # Используем client для регистрации
    response_register = client.post('/auth/register', json=user_data)
    assert response_register.status_code == status.HTTP_200_OK

    # --- Шаг 2: Логинимся ---
    login_data = {
        "username": "test_user",
        "password": "strongpassword123"
    }
    response_login = client.post('/auth/login', data=login_data)
    assert response_login.status_code == status.HTTP_200_OK

    # --- Шаг 3: "Вытаскиваем" токен и формируем заголовок ---
    token_data = response_login.json()
    access_token = token_data["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Возвращаем заголовок, который будет использоваться в тесте
    yield headers