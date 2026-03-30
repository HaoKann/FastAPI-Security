import asyncpg
from uuid import UUID

class ProductRepository:
    """
    Класс, который отвечает ТОЛЬКО за работу с базой данных (SQL).
    Никакой проверки прав, никакого Redis здесь быть не должно.
    """
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_all_by_user(self, username: str, limit: int, offset: int):
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT id, name, price, owner_username FROM products WHERE owner_username = $1 LIMIT $2 OFFSET $3",
                username, limit, offset 
            )
            return [dict(p) for p in records]
        
    async def create(self, name: str, price: float, username: str):
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "INSERT INTO products (name, price, owner_username) VALUES ($1, $2, $3 ) RETURNING *",
                name, price, username
            )
            return dict(record) if record else None
        
    
    async def get_by_id(self, product_id: UUID):
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM products WHERE id = $1",
                product_id
            )
            return dict(record) if record else None
        
    async def delete(self, product_id: UUID):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM products WHERE id = $1", product_id)

    async def update(self, product_id: UUID, name: str | None, price: float | None):
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                '''
                UPDATE products
                SET name = COALESCE($1, name),
                    price = COALESCE($2, price)
                WHERE id = $3
                RETURNING * 
                ''',
                name, price, product_id
            )
            return dict(record) if record else None
        
    
