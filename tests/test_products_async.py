import pytest
from httpx import AsyncClient
from starlette import status

# Этот декоратор обязателен для асинхронных тестов в pytest
@pytest.mark.asyncio
async def test_get_products_async(ac: AsyncClient, auth_headers: dict):
    """
    Асинхронный тест получения продуктов.
    Использует:
    - ac: Асинхронный клиент
    - auth_headers: Наш помощник с токеном 
    """

    # ВАЖНО: Здесь обязательно писать 'await'
    response = await ac.get('/products/', headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK

    # ВАЖНО: методы ответа (.json()) в httpx синхронные, await не нужен
    assert response.json() == []
