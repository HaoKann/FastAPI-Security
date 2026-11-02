import pytest
from unittest.mock import AsyncMock, MagicMock
from services.product_service import ProductService

@pytest.mark.asyncio
async def test_get_product_by_id():
    # 1. Создаем фейковый репозиторий
    mock_repo = AsyncMock()
    
    # Фейковые данные, которые "вернет" база
    fake_product = {'id': 1, 'name': 'test_name', 'price': 100}
    mock_repo.get_by_id.return_value = fake_product
    # 2. Создаем сервис, передавая ему нашу подделку вместо реальной базы
    service = ProductService(repository=mock_repo)
    
    result = await service.get_product_by_id(fake_product['id'])
    
    assert result == fake_product
    
    
    