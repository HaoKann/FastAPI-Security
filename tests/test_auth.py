from fastapi.testclient import TestClient
from fastapi import status

# --- Тесты для эндпоинта /auth/register ---
def test_register_user_success(client: TestClient):
    # Шаг 1: Готовим данные нового пользователя
    user_data = {
        "username": "new_test_user",
        "password": "strongpassword123"
    }

    # Шаг 2: Отправляем POST-запрос на /auth/register
    response = client.post('/auth/register', json=user_data)

    # Шаг 3: Проверяем результат
    assert response.status_code == status.HTTP_200_OK # Ожидаем успешный ответ
    response_data = response.json()
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert response_data['token_type'] == 'bearer'

def test_register_user_already_exists(client: TestClient):
    # Шаг 1: Готовим данные пользователя, которого мы сейчас создадим
    user_data = {
        "username": "existing_user",
        "password": "password123"
    }

    # Шаг 2: Регистрируем его в первый раз (ожидаем успеха)
    response1 = client.post('/auth/register', json=user_data)
    assert response1.status_code == status.HTTP_200_OK

    # Шаг 3: Пытаемся зарегистрировать его еще раз с теми же данными
    response2 = client.post('/aut/register', json=user_data)

    # Шаг 4: Проверяем, что сервер вернул ошибку
    assert response2.status_code == status.HTTP_400_BAD_REQUEST # Ожидаем ошибку "Bad Request"
    assert response2.json() == {'detail': 'Пользователь с таким именем уже существует'}



