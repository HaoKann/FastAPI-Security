from jose import jwt
from datetime import datetime, timedelta, UTC
from fastapi.testclient import TestClient
from starlette import status

# Мы берем настройки прямо из модуля авторизации.
# Если в CI задан env var, auth.py его подхватит, и тест тоже его увидит.
from auth import SECRET_KEY, ALGORITHM

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
    assert response.status_code == 403
    assert response.json() == {'detail': 'Not authenticated'}

def test_protected_with_token(client):
    # Создаём тестовый токен
    to_encode = {'sub': 'testuser', 'type': 'access'}
    expire = datetime.now(UTC) + timedelta(minutes=30)
    to_encode.update({'exp': expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    response = client.get('/auth/protected', headers={'Authorization': f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {'message': 'Привет, testuser! Это защищенная зона'}


def test_protected_with_invalid_token(client: TestClient):
    """
    Проверяет, что эндпоинт /protected возвращает 401,
    если прислать поддельный (невалидный) токен.
    """

    # --- Шаг 1: Придумываем поддельный токен ---
    # Нам не нужно регистрироваться или логиниться. 
    # Мы просто берем строку, которая *похожа* на токен,
    # но которую твой сервер точно не подписывал.
    invalid_token = "ueiruiewruiewgrigewirgbewrgewhjrewrhwerhieuwhriwehrwe3123122"

    # --- Шаг 2: Формируем заголовки ---
    headers = {
        "Authorization": f"Bearer {invalid_token}"
    }

    # --- Шаг 3: Делаем запрос к /protected с поддельным токеном ---
    response_protected = client.get('/auth/protected', headers=headers)

    # --- Шаг 4: Проверяем, что нас не пустили ---
    # Ожидаем ошибку 401 Unauthorized
    assert response_protected.status_code == status.HTTP_401_UNAUTHORIZED

    # (Опционально) Проверяем тело ошибки, если твой get_current_user
    # возвращает конкретное сообщение
    data = response_protected.json()
    assert "detail" in data
    # Например, если у тебя там "Could not validate credentials"
    # assert data["detail"] == "Could not validate credentials"