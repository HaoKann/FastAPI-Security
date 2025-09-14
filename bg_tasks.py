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

# ИСПРАВЛЕНО: Загружаем переменные окружения прямо здесь
# чтобы Celery-воркер гарантированно их увидел.
load_dotenv()

# Импортируем наш главный объект Celery
from celery_worker import celery_app
from auth import get_current_user


# Получаем логгер. __name__ автоматически подставит "bg_tasks"
logger = logging.getLogger(__name__)


# Создаем APIRouter. Все эндпоинты в этом файле будут привязаны к нему.
# APIRouter это как локальный 'удлинитель' к которому будут подключены все эндпоинты
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

@celery_app.task(bind=True, name='compute_factorial_task')
def compute_factorial_task(self, username: str, n: int):
    """
    Celery-задача для вычисления факториала с механизмом повторных попыток.
    Эта функция ВЫЗЫВАЕТСЯ синхронно, но ВНУТРИ запускает асинхронный код.
    """
    logger.info(f'[CELERY] Попытка {self.request.retries + 1}. Начато вычисление факториала {n} для {username}')

    # Вся асинхронная логика теперь находится внутри этой вложенной функции
    async def _run_async_logic():
    # Симуляция долгой работы
        try:
            await asyncio.sleep(5)
            result = 1
            for i in range(1, n + 1):
                result *= i

            # ИСПРАВЛЕНО: Формируем правильную DSN-строку в формате URL
            # Подключаемся к БД, используя DSN из .env
            DATABASE_URL = (f"postgres://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
                            f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")

            # Отладочный вывод: печатаем адрес, по которому пытаемися подключиться
            logger.info(f"[CELERY DEBUG] Пытаюсь подключиться по адресу {DATABASE_URL.replace(os.getenv('DB_PASSWORD'), '********' )}")

    # Напрямую работаем с БД, без вложенных функций
            conn = await asyncpg.connect(dsn=DATABASE_URL)
            try:
                await conn.execute(
                        'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                        username, f"factorial of {n}", result
                    )
            finally:
                await conn.close()

            logger.info(f'[CELERY] Успешно вычислен факториал {n} = {result}')
            return result
    
        except Exception as e:
            logger.warning(f'[CELERY] Ошибка при выполнении задачи: {e}. Попытка повтора...')
            # Используем встроенный механизм retry от Celery
            # exc=e передает оригинальную ошибку e внутрь механизма повторных попыток Celery
            raise self.retry(exc=e, countdown=5, max_retries=3)

    # Запускаем нашу асинхронную функцию и ждем ее завершения.
    # Это решает проблему "coroutine is not JSON serializable".
    return asyncio.run(_run_async_logic())

# Celery задача compute_sum_range, которая вычисляет сумму чисел в заданном диапазоне асинхронно.
@celery_app.task(bind=True, name='compute_sum_range_task')
def compute_sum_range_task(self, start: int, end: int, username: str):
    """
    Celery-задача для вычисления суммы в диапазоне.
    Выполняется отдельным процессом-воркером.
    """
    logger.info(f"[CELERY] Попытка {self.request.retries + 1}. Начало вычисления суммы от {start} до {end} для {username}")

    async def _run_async_logic():
        try:
            await asyncio.sleep(3)
            result = sum(range(start, end + 1))

            DATABASE_URL = (f"postgres://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
                            f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")

            logger.info(f"[CELERY DEBUG] Пытаюсь подключиться по адресу: {DATABASE_URL.replace(os.getenv('DB_PASSWORD'), '********')}")

            conn = await asyncpg.connect(dsn=DATABASE_URL)
            try:
                await conn.execute(
                        'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                        username, f"sum from {start} to {end}", result
                    )
            finally:
                await conn.close()
                    
            logger.info(f"[CELERY] Успешно вычислена сумма от {start} до {end} = {result}")
            return result
        except Exception as e:
            logger.warning(f'[CELERY] Ошибка при выполнении задачи: {e}. Попытка повтора...')
            raise self.retry(exc=e, countdown=5, max_retries=3)
    
    return asyncio.run(_run_async_logic())

        
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
