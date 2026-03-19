from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from uuid import UUID
import json

# Импортируем наш репозиторий
from repositories.product_repository import ProductRepository

class ProductService:
    def __init__(self, repository: ProductRepository, redis=None, background_tasks=None, manager=None):
        self.repo = repository
        self.redis = redis
        self.background_tasks = background_tasks
        self.manager = manager

    async def _clear_cache(self, username: str):
        """Вспомогательный метод для очистки кэша юзера"""
        if self.redis:
            try:
                cached_keys = await self.redis.keys(f"products:{username}:*")
                if cached_keys:
                    await self.redis.delete(*cached_keys)
                    print(f"🧹 Кэш сброшен для пользователя {username}")
            except Exception as e:
                print(f"⚠️ Ошибка сброса кэша: {e}")

    async def get_products(self, username: str, limit: int, offset: int):
        CACHE_KEY = f"products:{username}:{limit}:{offset}"

        # 1. Проверяем кэш
        if self.redis:
            try:
                cached_data = await self.redis.get(CACHE_KEY)
                if cached_data:
                    print(f"✅ CACHE HIT: Товары для пользователя {username} из Redis")
                    return json.loads(cached_data)
            except Exception as e:
                pass # Игнорируем ошибку чтения и идем в БД


        # 2. Идем в базу через Репозиторий!
        print(f"❌ CACHE MISS: Идем в базу за товарами для {username}")
        records = await self.repo.get_all_by_user(username, limit, offset)
        products_data = jsonable_encoder(records)
        
        # 3. Сохраняем в кэш
        if self.redis:
            try:
                await self.redis.set(CACHE_KEY, json.dumps(products_data), ex=60)
            except Exception:
                pass

        return products_data
