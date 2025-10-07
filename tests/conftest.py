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
    # --- 2. Создаем наши "помощники" (фикстуры) ---
except Exception as e:
    print(f"Error importing app: {e}")
    raise

@pytest.fixture(scope='function')
def db_pool(monkeypatch):
    existing_users = set() # пустое множество — пользователей ещё нет

    async def mock_get_user_from_db(pool, username):
        # Возвращаем "пользователя", если он уже зарегистрирован
        if username in existing_users:
            return {'username': username, 'hashed_password': 'hashed_password'}
        return None
    
    async def mock_execute(conn, query, *args):
        # Когда кто-то вызывает INSERT INTO users, добавляем юзера в список
        if "INSERT INTO users" in query and len(args) >= 1:
            existing_users.add(args[0])

    # Мокаем get_user_from_db и execute
    monkeypatch.setattr('auth.get_user_from_db', mock_get_user_from_db)
    monkeypatch.setattr('asyncpg.Connection.execute', mock_execute)

    # Мокаем get_pool, чтобы register мог получить соединение
    def mock_get_pool():
        class MockPool:
            async def acquire(self):
                class MockConnection:
                    async def execute(self, query, *args):
                        await mock_execute(self, query, *args)
                return MockConnection()
        return MockPool()
    
    monkeypatch.setattr('database.get_pool', mock_get_pool)
    return None


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

        # Код после `yield` выполнится после того, как все тесты в файле завершатся.
        # Здесь можно было бы, например, очищать тестовые данные.

# В будущем мы будем добавлять сюда другие фикстуры, 
# например, для создания тестового пользователя в базе данных.