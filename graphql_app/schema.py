import strawberry

# --- 1. Описываем, какие вопросы (Queries) можно задать ---
@strawberry.type
class Query:

    # Это поле 'hello'. Оно возвращает строку.
    @strawberry.field
    def hello(self) -> str:
        return "Привет! Это первый GraphQL ответ 🍓"
    
    # Добавим простую арифметику для примера
    @strawberry.field
    def add(self, a: int, b: int) -> int:
        return a + b
    
# --- 2. Собираем всё в схему ---
schema = strawberry.Schema(query=Query)