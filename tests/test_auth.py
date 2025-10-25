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
    response2 = client.post('/auth/register', json=user_data)

    # Шаг 4: Проверяем, что сервер вернул ошибку
    assert response2.status_code == status.HTTP_400_BAD_REQUEST # Ожидаем ошибку "Bad Request"
    assert response2.json() == {'detail': 'Пользователь с таким именем уже существует'}



def test_login_success(client: TestClient):
    """
    Тест успешного входа в систему.
    1. Сначала регистрируем пользователя.
    2. Потом логинимся с теми же данными.
    """

    # Шаг 1: Регистрируем пользователя
    # "Правильный" пароль должен совпадать с тем, что зашит в mock_verify_password
    user_data = {
        "username": "login_user",
        "password": "strongpassword123"
    }
    response_register = client.post('/auth/register', json=user_data)
    assert response_register.status_code == status.HTTP_200_OK

    # Шаг 2: Пытаемся залогиниться
    # ВАЖНО: FastAPI для /token ожидает данные в виде form data, а не JSON!
    # Поэтому мы используем 'data=', а не 'json='
    login_data = {
        "username": "login_user",
        "password": "strongpassword123"
    }
    response_login = client.post('/auth/login', data=login_data)

    # Шаг 3: Проверяем результат
    assert response_login.status_code == status.HTTP_200_OK
    data = response_login.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_user_not_found(client: TestClient):
    """
    Тест входа с несуществующим пользователем.
    """
    login_data = {
        "username": "ghost_user", # Этот пользователь НЕ был зарегистрирован
        "password": "any_password"
    }
    response_login = client.post('/auth/login', data=login_data)

    # Ожидаем ошибку 401 Unauthorized (или 404, в зависимости от логики)
    # 401 более безопасен, т.к. не говорит, что именно неверно (логин или пароль)
    assert response_login.status_code == status.HTTP_401_UNAUTHORIZED
    data = response_login.json()
    assert "access_token" not in data
    assert "detail" in data


def test_login_wrong_password(client: TestClient):
    """
    Тест входа с неправильным паролем.
    """
    # Шаг 1: Регистрируем пользователя
    user_data = {
        "username": "wrong_pass_user",
        "password": "strongpassword123" # "Правильный" пароль
    }
    response_register = client.post('/auth/register', json=user_data)
    assert response_register.status_code == status.HTTP_200_OK

    # Шаг 2: Пытаемся залогиниться с неверным паролем
    login_data = {
        "username": "wrong_pass_user",
        "password": "this_is_wrong_password" # "Неправильный" пароль
    }
    response_login = client.post('/auth/login', data=login_data)

    # Шаг 3: Проверяем результат
    assert response_login.status_code == status.HTTP_401_UNAUTHORIZED
    data = response_login.json()
    assert "access_token" not in data
    assert "detail" in data
