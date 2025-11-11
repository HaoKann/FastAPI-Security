# conftest.py — это глобальный файл конфигурации pytest.
# Любые фикстуры, объявленные здесь, доступны во всех тестах, без импортов.

import pytest
from fastapi.testclient import TestClient
import os
from starlette import status

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

    # mock_get_user_from_db, которая имитирует поведение реальной функции:
    async def mock_get_user_from_db(pool, username):
        print("mock_get_user_from_db вызван, pool=", type(pool))
        # если пользователь уже существует, возвращает фейкового юзера, иначе None.
        if username in existing_users:
            return {'username': username, 'hashed_password': 'hashed_password'}
        return None
    
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
                        "id": fake_product_id_counter,
                        "name": args[0],
                        "price": args[1],
                        "owner_username": args[2]
                    }
                    fake_products_db.append(new_product)
                    fake_product_id_counter += 1
                    print(f"TESTING mode: Продукт '{new_product['name']}' добавлен в mock DB.")
                    return new_product
                
                # --- Старый код для get_user_from_db ---
                if "SELECT" in query and "users" in query:
                    if args and args[0] in existing_users:
                        return {'username': args[0], 'hashed_password': 'hashed_password'}
                
                print(f"TESTING mode: mock fetchrow получил неизвестный запрос: {query[:30]}...")
                return None
            
            # имитирует conn.fetch(...)
            async def fetch(self, query, *args):
                if "SELECT" in query and "products" in query and "WHERE owner_username" in query:
                    owner_username = args[0]
                    # Ищем в фейковой базе
                    user_products = [p for p in fake_products_db if p["owner_username"] == owner_username]
                    print(f"TESTING mode: Найдены продукты для '{owner_username}': {len(user_products)} шт. ")
                    return user_products
                
                print(f"TESTING mode: mock fetch получил неизвестный запрос: {query[:30]}...")
                return []
            
            # имитирует conn.execute(...)
            async def execute(self, query, *args):
                # Эмулируем INSERT INTO users (username, hashed_password) VALUES ($1, $2)
                if isinstance(query, str) and "INSERT INTO users" in query and len(args) >= 1:
                    
                    # === ГЛАВНОЕ ИСПРАВЛЕНИЕ ===
                    # Получаем доступ к "фейковой" БД
                    global existing_users

                    # Добавляем пользователя (первый аргумент, $1)
                    existing_users.add(args[0])

                    print(f"TESTING mode: User '{args[0]}' УСПЕШНО ДОБАВЛЕН в mock DB.")
                    return "OK"
                    
                # Если это был не INSERT, то просто выводим лог
                print(f"TESTING mode: (Query: '{query[:30]}...') - не INSERT пользователя, пропускаем.")
                return "OK"
            
            # async def __aenter__ и async def __aexit__ — позволяют использовать объект в async with (контекстный менеджер)
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
            
        # MockPool — имитирует пул соединений:
        class MockPool:
            async def acquire(self):
                return MockConnection()
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
        
        return MockPool()
    
    # Эта "обманка" будет имитировать проверку пароля
    def mock_verify_password(plain_password, hashed_password):
        print(f"mock_verify_password вызвана: '{plain_password}' vs '{hashed_password}")
        # Мы знаем, что наш фейковый хеш - это 'hashed_password'
        # А "правильный" пароль мы будем использовать в тестах "strongpassword123"
        if hashed_password == 'hashed_password' and plain_password == 'strongpassword123':
            return True
        # Если пароль другой, проверка не пройдена
        return False

    # "Подменяем" настоящую функцию проверки пароля на нашу "обманку"
    try:
        monkeypatch.setattr('auth.verify_password', mock_verify_password)
        print("Mocking 'auth.verify_password' successful")
    except (ImportError, AttributeError):
        print("!!! Не удалось найти 'auth.hashing.verify_password'.")
        print("!!! Проверь путь и название твоей функции верификации пароля.")


    # Подменяем реальные функции/объекты
    monkeypatch.setattr('auth.get_user_from_db', mock_get_user_from_db)
    # Подменяем get_pool (функцию) — приложение вызывает get_pool() и получит MockPool
    monkeypatch.setattr('database.get_pool', mock_get_pool)

    # Добавляем фейковый пул прямо в приложение
    from main import app
    app.state.pool = mock_get_pool()

    # Принудительно подменяем get_pool() на возвращение MockPool()
    from database import get_pool as real_get_pool
    
    async def fake_get_pool():
        return mock_get_pool()
    
    monkeypatch.setattr('auth.get_pool', fake_get_pool)
    app.dependency_overrides[real_get_pool] = fake_get_pool


    # Фикстура db_pool не обязана возвращать объект — она просто настраивает окружение (патчит модули)
    return None



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