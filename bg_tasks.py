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
from dotenv import load_dotenv
import os

# --- 1. Импорты и настройка ---

# Импортируем наш главный объект Celery
from celery_worker import celery_app
from auth import get_current_user

# ИСПРАВЛЕНО: Загружаем переменные окружения прямо здесь
load_dotenv()

# ИСПРАВЛЕНО: Модуль сам определяет строку подключения к БД, читая ее из .env
DB_CONNINFO = (f"host={os.getenv('DB_HOST')} port={os.getenv('DB_PORT')} "
               f"dbname={os.getenv('DB_NAME')} user={os.getenv('DB_USER')} "
               f"password={os.getenv('DB_PASSWORD')}")


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
    await asyncio.sleep(5)
    
    result = 1
    for i in range(1, n + 1):
        result *= i

    # Напрямую работаем с БД, без вложенных функций
    conn = await asyncpg.connect(dsn=DB_CONNINFO)
    try:
        await conn.execute(
                'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                username, f"factorial of {n}", result
            )
    finally:
        await conn.close()

    logger.info(f'[CELERY] Успешно вычислен факториал {n} = {result}')
    return result


# Celery задача compute_sum_range, которая вычисляет сумму чисел в заданном диапазоне асинхронно.
@celery_app.task(name='compute_sum_range_task')
async def compute_sum_range_task(start: int, end: int, username: str):
    """
    Celery-задача для вычисления суммы в диапазоне.
    Выполняется отдельным процессом-воркером.
    """
    logger.info(f"[CELERY] Начало вычисления суммы от {start} до {end} для {username}")
    await asyncio.sleep(3)
    result = sum(range(start, end + 1))

   
    conn = await asyncpg.connect(dsn=DB_CONNINFO)
    try:
        await conn.execute(
                'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                username, f"sum from {start} to {end}", result
            )
    finally:
        await conn.close()
            
    # Запускаем асинхронную функцию внутри синхронной задачи Celery
    logger.info(f"[CELERY] Успешно вычислена сумма от {start} до {end} = {result}")
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




@router.post('/sum', status_code=status.HTTP_202_ACCEPTED)
async def start_sum_computation(request: SumRequest, current_user: dict = Depends(get_current_user) ):
    """Запускает вычисление суммы в диапазоне в фоновом режиме."""
    if request.start > request.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Начало диапозона не может быть больше конца')
    
    username = current_user['username']
    compute_sum_range_task.delay(start = request.start, end = request.end, username = username)
    return {'message': f'Вычисление суммы от {request.start} до {request.end} начато в фоне'}
