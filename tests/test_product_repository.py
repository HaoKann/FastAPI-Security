import pytest
from unittest.mock import AsyncMock, MagicMock
from repositories.product_repository import ProductRepository


def create_fake_product():
    fake_product = MagicMock()
    fake_product.id = 1
    fake_product.name = 'test_product'
    fake_product.price = 99.9
    fake_product.description = 'test_product_description'
    fake_product.owner.username = 'test_owner'
    fake_product.owner.avatar_url = 'http://test_avatar.url'
    return fake_product


@pytest.mark.asyncio
async def test_get_by_id_success():
    # 1. Create our fake database session and repository
    mock_db = AsyncMock()
    repo = ProductRepository(db=mock_db)
    
    # 2. Create a fake Product object that the database will "find"
    fake_product = create_fake_product()
    
    # 3. Create the fake result object that comes back from db.execute()
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = fake_product
    
    # 4. Call the method
    result = await repo.get_by_id(1)
    
    assert result['id'] == 1
    assert result['name'] == 'test_product'
    assert result['price'] == 99.9
    assert result['owner_username'] == 'test_owner'
    
    
@pytest.mark.asyncio
async def test_get_by_id_not_found():
    
    mock_db = AsyncMock()
    repo = ProductRepository(db=mock_db)
    mock_result = MagicMock()
    
    mock_db.execute.return_value = mock_result
    mock_result.scalar_one_or_none.return_value = None
    
    result = await repo.get_by_id(1)
    
    assert result is None
    
    
@pytest.mark.asyncio
async def test_get_all_products_success():
    mock_db = AsyncMock()
    repo = ProductRepository(db=mock_db)
    mock_result = MagicMock()
    
    mock_db.execute.return_value = mock_result
    
    fake_product = create_fake_product()
    mock_result.scalars.return_value.all.return_value = [fake_product]
    
    result = await repo.get_all_products(5, 1)
    
    assert result[0]['id'] == 1


@pytest.mark.asyncio
async def test_get_all_products_none():
    mock_db = AsyncMock()
    repo = ProductRepository(db=mock_db)
    mock_result = MagicMock()
    
    mock_db.execute.return_value = mock_result
    
    mock_result.scalars.return_value.all.return_value = []
    
    result = await repo.get_all_products(5, 1)
    
    assert result == []
    
    
@pytest.mark.asyncio
async def test_get_all_by_user_success():
    mock_db = AsyncMock()
    repo = ProductRepository(db=mock_db)
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result
    
    fake_product = create_fake_product()
    mock_result.scalars.return_value.all.return_value = [fake_product]
    
    result = await repo.get_all_by_user('test_owner', 5, 1)
    
    assert result[0]['owner_username'] == 'test_owner'
    
    
@pytest.mark.asyncio
async def test_delete_success():
    mock_db = AsyncMock()
    repo = ProductRepository(db=mock_db)
    
    await repo.delete(1)
    
    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_success():
    mock_db = AsyncMock()
    repo = ProductRepository(db=mock_db)
    mock_result = MagicMock()
    mock_db.execute.return_value = mock_result
    
    fake_product = create_fake_product()
    mock_result.scalar_one_or_none.return_value = 1
    repo.get_by_id = AsyncMock(return_value=fake_product)
    
    result = await repo.create('test_product', 99.9, 'test_owner', 'test_owner')
    mock_db.commit.assert_awaited_once()
    
    
    assert result.id == 1