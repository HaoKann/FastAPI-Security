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


# --- 2. Резолверы

# ЧТЕНИЕ
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


# ЧТЕНИЕ ОДНОГО ТОВАРА
# Обрати внимание: возвращаем Optional[ProductType], так как товара может и не быть
async def get_product(info: Info, product_id: int) -> Optional[ProductType]:
    request = info.context['request']
    pool = request.app.state.pool

    if not pool:
        raise Exception("Нет подключения к БД!")

    async with pool.acquire() as connection:
        # Используем WHERE id = $1
        query = "SELECT id, name, description, price FROM products WHERE id = $1"
        row = await connection.fetchrow(query, product_id)

        if row:
            return ProductType(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                price=row["price"]
            )
        else:
            return None # Если не нашли, возвращаем null


# ЗАПИСЬ
async def create_product(info: Info, name: str, price: int, description: Optional[str] = None) -> ProductType:
   request = info.context['request']
   pool = request.app.state.pool

   if not pool:
       raise Exception('Нет подключения к БД!')

   async with pool.acquire() as connection:
        # Мы делаем INSERT и сразу просим вернуть ID созданной строки (RETURNING id)
        # Это фишка PostgreSQL, чтобы не делать два запроса.
        query = """
            INSERT INTO products (name, description, price)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        # Используем fetchrow, так как ожидаем ровно одну строку ответа (id)
        row = await connection.fetchrow(query, name, description, price)
        new_id = row['id']

        # Возвращаем созданный объект, чтобы клиент сразу увидел его ID
        return ProductType(id=new_id, name=name, description=description, price=price)
        

# --- 3. Структура API ---

# Список доступных вопросов (Queries)
@strawberry.type
class Query:

    # Старый hello для теста
    @strawberry.field
    def hello(self) -> str:
        return 'GraphQL работает!'
    
    # Новое поле products.
    # Мы говорим: "Это поле вернет СПИСОК (List) объектов ProductType".
    # resolver=get_products связывает это поле с функцией выше.
    # Список всех товаров
    products: List[ProductType] = strawberry.field(resolver=get_products)

    # Один конкретный товар
    # Мы указываем resolver=get_product. Strawberry увидит аргумент product_id в функции
    # и автоматически добавит его в схему API.
    product: Optional[ProductType] = strawberry.field(resolver=get_product)


# Список доступных действий (Mutations)
@strawberry.type
class Mutation:
    # Мы называем действие 'addProduct'. 
    # Strawberry поймет, какие аргументы нужны, посмотрев на функцию create_product
    add_product: ProductType = strawberry.field(resolver=create_product)




# --- 4. Сборка Схемы ---
# Важно: теперь передаем и query, и mutation
schema = strawberry.Schema(query=Query, mutation=Mutation)