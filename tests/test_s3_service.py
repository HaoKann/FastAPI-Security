import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from s3_service import S3Service

# 1. Простой тест: проверка работы без обращения к S3 при пустом имени
@pytest.mark.asyncio
async def test_get_presigned_url_empty_name():
    service = S3Service()
    
    # Передаем пустое имя файла
    result = await service.get_presigned_url("")
    
    # Ожидаем, что функция сразу вернет None
    assert result is None
    
    
# 2. Сложный тест: мокаем асинхронный клиент S3 для успешной генерации ссылки
@pytest.mark.asyncio
async def test_get_presigned_url_success():
    serivce = S3Service()
    expected_url = "https://s3.fake.com/my-bucket/avatar.png?token=123"
    
    # Шаг A: Создаем мок самого S3-клиента и задаем ответ для генерации ссылки
    mock_s3_client = AsyncMock()
    mock_s3_client.generate_presigned_url.return_value = expected_url
    
    # Шаг B: Настраиваем поддержку контекстного менеджера (async with)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_s3_client
    mock_ctx.__aexit__.return_value = None
    
    # Шаг C: Подменяем вызов service.session.client(...) нашим моком
    with patch.object(serivce.session, 'client', return_value=mock_ctx):
        # Если передали полный URL, функция должна отрезать до "avatar.png"
        result = await serivce.get_presigned_url("http://s3.com/bucket/avatar.png")
        
        # Проверки (Assertions)
        assert result == expected_url
        
        # Проверяем, что метод S3 был вызван ровно 1 раз и с правильным очищенным именем 'avatar.png'
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            ClientMethod='get_object',
            Params={'Bucket': serivce.bucket, 'Key': 'avatar.png'},
            ExpiresIn=3600
        )
        
# 3. Тест обработки ошибок: если S3 выбросил исключение
@pytest.mark.asyncio
async def test_get_presigned_url_exception():
    service = S3Service()
    
    # Настраиваем мок так, чтобы генерация ссылки вызывала ошибку
    mock_s3_client = AsyncMock()
    mock_s3_client.generate_presigned_url.side_effect = Exception("S3 Connection Error")
    
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_s3_client
    mock_ctx.__aexit__.return_value = None
    
    with patch.object(service.session, 'client', return_value=mock_ctx):
        result = await service.get_presigned_url('avatar.png')
        
    # В блоке except функция перехватывает ошибку и возвращает None
    assert result is None