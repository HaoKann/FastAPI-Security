from fastapi.testclient import TestClient

# --- Тесты для корневых эндпоинтов ---

def test_read_root(client: TestClient):
    """
    Проверяем, что главный эндпоинт ("/") работает и возвращает правильный статус.
    (client: TestClient): Наш "виртуальный Postman", который мы создали в conftest.py.
    Pytest автоматически найдет его и передаст сюда.
    """
    print('Starting test_read_root')
    # Шаг 1: Отправляем GET-запрос на адрес "/"
    response = client.get('/')
    print(f"Response status: {response.status_code}, JSON: {response.json()}")
    # Шаг 2: Проверяем результат (Утверждаем)
    assert response.status_code == 200
    assert response.json() == {'status': 'API is running.'}

def test_not_found(client: TestClient):
    print("Starting test_not_found")
    """
    Проверяем, что запрос к несуществующему пути возвращает ошибку 404 Not Found.
    """
    response = client.get('/a/b/c/d/e/f/g')
    print(f"Response status: {response.status_code}")
    assert response.status_code == 404

