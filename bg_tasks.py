# BackgroundTasks позволяет запускать задачи в фоне, не блокируя клиента.
# Подходят лёгких и быстрых задач: например, отправить письмо, записать лог, очистить временные файлы.
# Работает только пока живёт процесс FastAPI. Если сервер упал или перезапустился — задача пропадёт.

# Поддержка асинхронного программирования для не блокирующих операций.
import asyncio
# Модуль Python для записи логов (отладка, ошибки, информация).
import logging
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

# --- 1. Импорты и настройка ---

# Импортируем наш главный объект Celery
from celery_worker import celery_app
from auth import get_current_user
from database import DB_CONNINFO # Импортируем СТРОКУ подключения, а не сам пул


# Получаем логгер. __name__ автоматически подставит "bg_tasks"
logger = logging.getLogger(__name__)


# Создаем APIRouter. Все эндпоинты в этом файле будут привязаны к нему.
# APIRouter это как локальный 'удлинитель' к которму будут подключены все эндпоинты
router = APIRouter(
    prefix='/compute', # Все пути будут начинаться с /compute
    tags=['Background Tasks'], # Группировка в документации Swagger
    dependencies=[Depends(get_current_user)] # Все эндпоинты здесь требуют авторизации
)

# --- 2. Модели Pydantic для эндпоинтов ---
class FactorialRequest(BaseModel):
    n: int

class SumRequest(BaseModel):
    start: int
    end: int



# --- 3. Определяем задачи Celery ---
# ВАЖНО: Мы больше не используем декоратор @retry от tenacity,
# так как у Celery есть свои, более мощные механизмы для повторных попыток.
@celery_app.task(name='compute_factorial_task')
async def compute_factorial_task(username: str, n: int):
    """
    Celery-задача для вычисления факториала.
    Эта функция выполняется НЕ в приложении FastAPI, а отдельным процессом-воркером.
    """
    logger.info(f'[CELERY] Начато вычисление факториала {n} для {username}')

    # Симуляция долгой работы
    import time
    time.sleep(5)

    result = 1
    for i in range(1, n + 1):
        result *= i

    # ВАЖНО: Задача сама управляет своим подключением к БД.
    async def save_to_db():
        conn = await asyncpg.connect(dsn=DB_CONNINFO)
        try:
            await conn.execute(
                    'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                    username, f"factorial of {n}", result
                )
        finally:
            await conn.close()

        # Запускаем асинхронную функцию внутри синхронной задачи Celery
        asyncio.run(save_to_db())

        logger.info(f'[CELERY] Успешно вычислен факториал {n} = {result}')
        return result



# --- 4. Эндпоинты, которые ставят задачи в очередь ---

@router.post('/factorial', status_code=status.HTTP_202_ACCEPTED)
async def start_factorial_computation(
    request: FactorialRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Принимает запрос и отправляет задачу на вычисление факториала в очередь Celery.
    """
    if request.n <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    
    username = current_user['username']

    # Отправляем задачу в очередь Redis.
    # Celery-воркер подхватит ее и выполнит.
    compute_factorial_task.delay(username=username, n=request.n)

    return {'message': f'Задача по вычислению факториала {request.n} принята в обработку'}





# Функция compute_sum_range, которая вычисляет сумму чисел в заданном диапазоне асинхронно.
# @retry - декоратор из библиотеки tenacity, который позволяет повторить выполнение функции до 3 раз с интервалом 2 секунды, 
# если она завершится с ошибкой. Это полезно для обработки временных сбоев (например, с базой данных).

async def compute_sum_range_task(pool: asyncpg.Pool, start: int, end: int, username: str, background_tasks: BackgroundTasks):
    """Асинхронно вычисляет сумму в диапазоне и сохраняет результат."""
    try:
        logger.info(f"Начало вычисления суммы от {start} до {end} для {username}")
        await asyncio.sleep(3) # Симуляция длительной задачи
        result = sum(range(start, end + 1))

        async with pool.acquire() as conn: # Используем acquire для asyncpg
                await conn.execute(
                    'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                    username, f"sum from {start} to {end}", result
                )
        logger.info(f"Успешно вычислена сумма от {start} до {end} = {result}")
        background_tasks.add_task(notify_completion, username, result, f'Сумма от {start} до {end}' )
    except Exception as e:
        logger.error(f"Ошибка при вычислении суммы: {str(e)}")
        # Передаёт исключение дальше, чтобы оно было обработано вызывающим кодом.
        raise




@router.post('/sum')
async def start_sum_computation(
    start: int, 
    end: int, 
    background_tasks: BackgroundTasks, 
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool)
):
    """Запускает вычисление суммы в диапазоне в фоновом режиме."""
    if start > end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Начало диапозона не может быть больше конца')
    
    username = current_user['username']
    background_tasks.add_task(compute_sum_range_task, pool, start, end, username, background_tasks)
    return {'message': f'Вычисление суммы от {start} до {end} начато в фоне'}
