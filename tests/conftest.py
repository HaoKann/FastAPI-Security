# conftest.py — это глобальный файл конфигурации pytest.
# Любые фикстуры, объявленные здесь, доступны во всех тестах, без импортов.

from main import app
from database import get_pool as original_get_pool
import pytest
from fastapi.testclient import TestClient
import os
from starlette import status
from websocket import manager
from httpx import AsyncClient, ASGITransport


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
    """
    Создает фейковую базу и подменяет зависимости.
    Возвращает экземпляр MockPool.
    """
    global existing_users, fake_products_db, fake_product_id_counter
    existing_users.clear()  # очищаем перед каждым тестом
    fake_products_db.clear()
    fake_product_id_counter = 1
    manager.active_connections = []

    # --- ОПРЕДЕЛЕНИЕ ФЕЙКОВЫХ ФУНКЦИЙ ---

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
                print(f"DEBUG fetchrow: {query[:50]}... args={args}")
                
                global fake_product_id_counter

                # 1. Создание продукта
                if "INSERT INTO products" in query:
                    new_product = {
                        "id": fake_product_id_counter, "name": args[0],
                        "price": args[1], "owner_username": args[2]
                    }
                    fake_products_db.append(new_product)
                    fake_product_id_counter += 1
                    print(f"TESTING mode: Продукт '{new_product['name']}' добавлен в mock DB.")
                    return new_product
                
                # 2. Поиск пользователя (для логина)
                if "SELECT" in query and "users" in query:
                    if args and args[0] in existing_users:
                        return {'username': args[0], 'hashed_password': 'hashed_password'}
                    return None

            # 3. Поиск продукта перед удалением (SELECT owner_username...)
                if "SELECT owner_username FROM products" in query:
                    product_id = int(args[0])
                    # Ищем продукт в списке
                    for p in fake_products_db:
                        if p['id'] == product_id:
                            return {"owner_username": p["owner_username"]}
                        return None
                    
                # 4. Обновление продукта (UPDATE ... RETURNING *)
                if "UPDATE products" in query:
                    product_id = int(args[2])
                    new_name = args[0]
                    new_price = args[1]

                    for i, p in enumerate(fake_products_db):
                        if p['id'] == product_id:
                            # Эмуляция COALESCE: если пришло None, оставляем старое
                            updated_name = new_name if new_name is not None else p['name']
                            updated_price = new_price if new_price is not None else p['price']

                            # Обновляем словарь в списке
                            fake_products_db[i]['name'] = updated_name
                            fake_products_db[i]['price'] = updated_price

                            print(f"TESTING mode: Продукт ID {product_id} обновлен.")
                            return fake_products_db[i] # Возвращаем обновленный словарь
                    return None
                
                return None


            # имитирует conn.fetch(...) для списков (SELECT * FROM ...)
            async def fetch(self, query, *args):
                if "SELECT" in query and "products" in query:
                   return [p for p in fake_products_db if p["owner_username"] == args[0]]
                return []
             
            # имитирует conn.execute(...) для INSERT (без возврата) и DELETE ---
            async def execute(self, query, *args):
                # 1. Регистрация пользователя
                # Эмулируем INSERT INTO users (username, hashed_password) VALUES ($1, $2)
                if isinstance(query, str) and "INSERT INTO users" in query:
                    # Получаем доступ к "фейковой" БД
                    global existing_users
                    # Добавляем пользователя
                    existing_users.add(args[0])
                    print(f"!!! УСПЕХ: User '{args[0]}' добавлен в mock DB.")
                    return "OK"
                
                # 2. Удаление продукта
                if "DELETE FROM products" in query:
                    product_id = int(args[0])
                    global fake_products_db
                    # Оставляем в списке только те продукты, у которых ID НЕ совпадает
                    initial_len = len(fake_products_db)
                    fake_products_db = [p for p in fake_products_db if p["id"] != product_id]

                    if len(fake_products_db) < initial_len:
                        print(f"!!! УСПЕХ: Продукт ID {product_id} удален из mock DB")
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

            async def close(self):
                pass
        
        return MockPool()
    

    # ПРИМЕНЯЕМ ПОДМЕНЫ 
    # А. Подменяем функции внутри auth.py

    # 1. Создаем экземпляр нашего фейкового пула
    mock_pool_instance = mock_get_pool()

    # 2. Кладем его в app.state (ЭТО ВАЖНО ДЛЯ GRAPHQL!)
    app.state.pool = mock_pool_instance

    # 3. Подменяем зависимость для REST API
    app.dependency_overrides[original_get_pool] = lambda: mock_pool_instance


    # Б. Подменяем ЗАВИСИМОСТЬ (Depends) во всем приложении
    # Это заменяет get_pool на mock_get_pool везде, где есть Depends(get_pool)
    monkeypatch.setattr('auth.get_user_from_db', mock_get_user_from_db)
    try:
        # "Подменяем" настоящую функцию проверки пароля на нашу "обманку"
        monkeypatch.setattr('auth.get_user_from_db', mock_get_user_from_db)
        monkeypatch.setattr('auth.verify_password', mock_verify_password)
    except AttributeError:
        pass
    
    # !!! ВАЖНО: Возвращаем сам пул, чтобы client мог его восстановить
    yield mock_pool_instance

    app.dependency_overrides = {}
    app.state.pool = None  # Очищаем после теста



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
    # TestClient запускает lifespan, который делает app.state.pool = None.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        # `yield` передает управление тесту, который запросил этого "помощника".
        print('TestClient created')
        app.state.pool = db_pool
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



@pytest.fixture(scope="function")
async def ac(db_pool):
    """
    Асинхронный клиент (AsyncClient) для тестов.
    Позволяет использовать await client.get(...)
    """
    # ASGITransport позволяет тестировать приложение без запуска реального сервера (как TestClient)

    # На всякий случай тоже восстанавливаем пул
    app.state.pool = db_pool

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac