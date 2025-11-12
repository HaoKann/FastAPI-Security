from fastapi.testclient import TestClient
from fastapi import status

# --- Тест 1: Проверка получения пустого списка ---
def test_get_products_empty(client: TestClient, auth_headers: dict):
    """
    Тест: GET /products (когда продуктов еще нет)
    Проверяем, что аутентифицированный пользователь 
    получает пустой список, а не ошибку.
    
    Фикстуры:
    - client: Наш "Postman"
    - auth_headers: Наш "помощник", который уже залогинился
    """
    # Вызываем эндпоинт, используя "волшебный" заголовок
    response = client.get('/products', headers=auth_headers)

    # Проверяем, что все прошло успешно (код 200)
    assert response.status_code == status.HTTP_200_OK

    # Проверяем, что тело ответа - это пустой список
    assert response.json() == []


# --- Тест 2: Успешное создание продукта ---
def test_create_product(client: TestClient, auth_headers: dict):
    """
    Тест: POST /products (успешное создание продукта)
    Проверяем, что пользователь может создать продукт.

    """
    # 1. Готовим данные для нового продукта
    product_data = {
        "name": "Игровой ПК 'Vortex'",
        "price": 1999.99
    }

    # 2. Отправляем POST-запрос с данными (json=) и заголовком (headers=)
    response = client.post("/products", json=product_data, headers=auth_headers)

    # 3. Проверяем, что сервер ответил "200 OK"
    assert response.status_code == status.HTTP_200_OK

    # 4. Проверяем, что сервер вернул нам созданный продукт
    data = response.json()
    assert data["name"] == "Игровой ПК 'Vortex'"
    assert data["price"] == 1999.99
    assert data["id"] is not None # Убеждаемся, что ID был присвоен

    # 5. Проверяем, что "владелец" - это наш 'test_user' из фикстуры
    assert data["owner_username"] == "test_user"


# --- Тест 3: Проверка получения списка после создания ---
def test_get_products_after_creation(client: TestClient, auth_headers: dict):
    """
    Тест: GET /products (после создания)
    Проверяем, что эндпоинт GET теперь возвращает продукт,
    который мы только что создали.
    """
    # --- Шаг 1: Сначала создаем продукт ---
    product_data = {
        "name": "Ноутбук 'Shadow'",
        "price": 1200.00
    }
    create_response = client.post("/products", json=product_data, headers=auth_headers)
    assert create_response.status_code == status.HTTP_200_OK

    # --- Шаг 2: Теперь запрашиваем список продуктов ---
    get_response = client.get("/products", headers=auth_headers)

    # Проверяем, что все Ок
    assert get_response.status_code == status.HTTP_200_OK

    # Проверяем, что в списке есть ровно 1 элемент
    data = get_response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Ноутбук 'Shadow'"
    assert data[0]["owner_username"] == "test_user"



# --- Тест 4: Проверка защиты роутера (без токена) ---
def test_create_product_unauthenticated(client: TestClient):
    """
    Тест: POST /products (без токена)
    Проверяем, что зависимость `Depends(get_current_user)`
    на уровне роутера работает и "выкидывает" неавторизованных.
    """
    product_data = {
        "name": "Украденный ПК",
        "price": 10.00
    }

    # Отправляем запрос БЕЗ auth_headers
    response = client.post("/products", json=product_data)

    # Ожидаем 401 Unauthorized (Нет доступа)
    assert response.status_code == status.HTTP_403_FORBIDDEN

