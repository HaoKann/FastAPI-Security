import strawberry
from strawberry.types import Info
from typing import Optional, List


# --- 1. Создаем "Слепок" товара (ProductType) ---
# Это то, как товар будет выглядеть для GraphQL.
# Поля должны совпадать с тем, что вернет база данных.
@strawberry.type
class ProductType:
    id: int
    name: str
    description: Optional[str] # Optional означает, что поле может быть null(пустым)
    price: int


# --- 2. Пишем Резолвер (функцию добычи данных) ---
# info: Info — это специальный параметр Strawberry, в нем лежит объект запроса
async def get_products(info: Info) -> List[ProductType]:
    # 1. Достаем объект request из контекста Strawberry
    request = info.context['request']

    # 2. Через request добираемся до пула соединений с БД
    pool = request.app.state.pool

    if not pool:
        raise Exception("Нет подключения к БД!")
    
    # 3. Делаем SQL-запрос
    async with pool.acquire() as connection:
        # Выбираем только те поля, которые нужны нашему ProductType
        query = "SELECT id, name, description, price FROM products"
        rows = await connection.fetch(query)

        # 4. Превращаем "сырые" строки БД в красивые объекты ProductType
        return [
            ProductType(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                price=row["price"]
            )
            for row in rows
        ]

# --- 3. Главный класс Query ---
@strawberry.type
class Query:

    # Старый hello для теста
    @strawberry.field
    def hello(self) -> str:
        return 'GraphQL работает!'
    
    # Новое поле products.
    # Мы говорим: "Это поле вернет СПИСОК (List) объектов ProductType".
    # resolver=get_products связывает это поле с функцией выше.
    products: List[ProductType] = strawberry.field(resolver=get_products)


# --- 4. Создаем схему ---
schema = strawberry.Schema(query=Query)