import pytest
from jose import jwt
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


SECRET_KEY = '26e73ab713b6d22c1b45a5f0db904c961f2ccd65d0541fb04a938a5c44e23c7f'
ALGORITHM= 'HS256'

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
    assert response.json() == {'status': 'API is running'}

def test_not_found(client: TestClient):
    print("Starting test_not_found")
    """
    Проверяем, что запрос к несуществующему пути возвращает ошибку 404 Not Found.
    """
    response = client.get('/a/b/c/d/e/f/g')
    print(f"Response status: {response.status_code}")
    assert response.status_code == 404

def test_protected_without_token(client):
    response = client.get('/auth/protected')
    assert response.status_code == 401
    assert response.json() == {'detail': 'Could not validate credentials'}

def test_protected_with_token(client):
    # Создаём тестовый токен
    to_encode = {'sub': 'testuser', 'type': 'access'}
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({'exp': expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    response = client.get('/auth/protected', headers={'Authorization': f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {'message': 'Привет, testuser! Это защищенная зона'}


