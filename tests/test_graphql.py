import pytest

# 1. Тест публичного запроса (Query)
# Используем фикстуру ac (AsyncClient) из твоего conftest.py
@pytest.mark.asyncio
async def test_grapql_hello(ac, db_pool):
    # Формируем GraphQL запрос
    query = """
    query {
        hello
    }
    """ 
    # Отправляем JSON {"query": "..."}
    response = await ac.post('/graphql', json={'query': query})
    
    assert response.status_code == 200
    data = response.json()
    assert data['data']['hello'] == 'GraphQL работает!'


# 2. Тест создания товара БЕЗ токена (Должен провалиться)
@pytest.mark.asyncio
async def test_create_product_unauthorized(ac, db_pool):
    mutation = """
    mutation {
        addProduct(name: "Hacker Item", price: 0, description: "Hack") {
            id
            name
        }
    }
    """
    response = await ac.post('/graphql', json={'query': mutation})
    
    assert response.status_code == 200 # GraphQL почти всегда возвращает 200, даже при ошибке внутри
    data = response.json()

    # Проверяем, что есть ошибки и нет данных
    assert data["data"] is None
    assert "errors" in data
    assert "Not authenticated" in data["errors"][0]["message"] or "Missing Authorization Header" in data["errors"][0]["message"]


# 3. Тест создания товара С токеном (Должен пройти)
@pytest.mark.asyncio
async def test_create_product_authorized(ac, db_pool, auth_headers): # auth_headers возьмем из фикстуры (conftest.py)
    mutation = """
    mutation {
        addProduct(name: "Test Item", price: 100, description: "From Pytest") {
            id
            name
            }
        }
    """

    response = await ac.post('/graphql', json={'query': mutation}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    # Ошибок быть не должно
    if "errors" in data:
        print(f"ОШИБКА GRAPHQL: {data['errors']}")


    assert "errors" not in data
    # Товар должен вернуться
    assert data["data"]["addProduct"]["name"] == "Test Item"
    assert data["data"]["addProduct"]["id"] is not None