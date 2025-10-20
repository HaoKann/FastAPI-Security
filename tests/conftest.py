# conftest.py — это глобальный файл конфигурации pytest.
# Любые фикстуры, объявленные здесь, доступны во всех тестах, без импортов.

import pytest
from fastapi.testclient import TestClient
import os

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

# scope='function' — значит, фикстура выполняется перед каждым тестом заново и "сбрасывается" после него.
# (Можно также scope='session', чтобы создавать один раз на все тесты.)
@pytest.fixture(scope='function')
def db_pool(monkeypatch):
    global existing_users
    existing_users.clear()  # очищаем перед каждым тестом

    # mock_get_user_from_db, которая имитирует поведение реальной функции:
    async def mock_get_user_from_db(pool, username):
        print("mock_get_user_from_db вызван, pool=", type(pool))
        # если пользователь уже существует, возвращает фейкового юзера, иначе None.
        if username in existing_users:
            return {'username': username, 'hashed_password': 'hashed_password'}
        return None
    
    # Вспомогательная функция для выполнения INSERT в "памяти"
    async def mock_insert_user(pool, username, hashed_password):
        existing_users.add(username)
    

    # Фейковый пул и соединение
    # mock_get_pool() — это фейковая (тестовая) замена реального пула соединений с базой (asyncpg.Pool).
    def mock_get_pool():
        # MockConnection — имитирует одно соединение.
        class MockConnection:
            # имитирует conn.fetchrow(...)
            async def fetchrow(self, query, *args):
                # Эмулируем SELECT username, hashed_password FROM users WHERE username = $1
                if args and args[0] in existing_users:
                    return {'username': args[0], 'hashed_password': 'hashed_password'}
                return None

            
            # имитирует conn.execute(...)
            async def execute(self, query, *args):
                # Эмулируем INSERT INTO users (username, hashed_password) VALUES ($1, $2)
                if isinstance(query, str) and "INSERT INTO users" in query and len(args) >= 1:
                    await mock_insert_user(None, args[0], None)
                    return "OK"
                return "OK"
            
            # async def __aenter__ и async def __aexit__ — позволяют использовать объект в async with (контекстный менеджер)
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, exc_type, exc, tb):
                pass
            
        # MockPool — имитирует пул соединений:
        class MockPool:
            async def acquire(self):
                return MockConnection()
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, exc_type, exc, tb):
                pass
        
        return MockPool()
    
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
