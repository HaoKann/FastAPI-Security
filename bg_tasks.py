# BackgroundTasks позволяет запускать тяжёлые задачи (как факториал) в фоне, не блокируя клиента.
# 1. Фоновые задачи (BackgroundTasks) — для тяжёлых вычислений



# tenacity для настройки повторных попыток задач при сбоях.
from tenacity import retry, stop_after_attempt, wait_fixed
# Поддержка асинхронного программирования для не блокирующих операций.
import asyncio
# Модуль Python для записи логов (отладка, ошибки, информация).
import logging
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from auth import get_current_user
from database import get_pool
# Импортируем manager из websocket.py, чтобы отправлять уведомления
# Это безопасно, так как websocket.py не импортирует ничего из bg_tasks.py
from websocket import manager

# Получаем логгер. __name__ автоматически подставит "bg_tasks"
logger = logging.getLogger(__name__)


# Создаем APIRouter. Все эндпоинты в этом файле будут привязаны к нему.
router = APIRouter(
    prefix='/compute', # Все пути будут начинаться с /compute
    tags=['Background Tasks'], # Группировка в документации
    dependencies=[Depends(get_current_user)] # Все эндпоинты здесь требуют авторизации
)

# --- Утилиты ---
# Добавление уведомлений
# Функцию для отправки уведомлений через WebSocket после завершения фоновых задач 
async def notify_completion(username: str, result: int, task_name: str):
    await asyncio.sleep(1) # Короткая задержка для симуляции
    await manager.broadcast(f"Уведомление для {username}: Задача {task_name} завершена! Результат: {result}")


# --- Логика фоновых задач ---

# Функция для симуляции тяжёлых вычислений. Это пример задачи, которую можно выполнить в фоне.
# Функция с повторными попытками
# Декоратор, который пытается выполнить функцию до 3 раз с паузой 2 секунды между попытками, если возникает ошибка.
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2)) 
async def compute_factorial_task(pool: asyncpg.Pool, n: int, username: str, background_tasks: BackgroundTasks):
    """Асинхронно вычисляет факториал и сохраняет результат в БД."""
    try:
        # Записывает начало задачи в лог
        logger.info(f"Начало вычисление факториала {n} для {username}")
        await asyncio.sleep(5) # Асинхронная задержка
        result = 1
        for i in range(1, n + 1):
            result *= i

        async with pool.acquire() as conn:
                await conn.execute(
                    'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                    username, f"factorial of {n}", str(result)
                )
        # Записывает успешное завершение.
        logger.info(f"Успешно вычислен факториал {n} = {result}")
        background_tasks.add_task(notify_completion, username, result, f'Факториал {n}')
    except Exception as e:
        logger.error(f"Ошибка при вычислении факториала {n}: {str(e)}")
        raise # Передаём ошибку дальше для retry

# Функция compute_sum_range, которая вычисляет сумму чисел в заданном диапазоне асинхронно.
# @retry - декоратор из библиотеки tenacity, который позволяет повторить выполнение функции до 3 раз с интервалом 2 секунды, 
# если она завершится с ошибкой. Это полезно для обработки временных сбоев (например, с базой данных).
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def compute_sum_range_task(pool: asyncpg.Pool, start: int, end: int, username: str, background_tasks: BackgroundTasks):
    """Асинхронно вычисляет сумму в диапазоне и сохраняет результат."""
    try:
        logger.info(f"Начало вычисления суммы от {start} до {end} для {username}")
        await asyncio.sleep(3) # Симуляция длительной задачи
        result = sum(range(start, end + 1))

        async with pool.acquire() as conn: # Используем acquire для asyncpg
                await conn.execute(
                    'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                    username, f"sum from {start} to {end}", str(result)
                )
        logger.info(f"Успешно вычислена сумма от {start} до {end} = {result}")
        background_tasks.add_task(notify_completion, username, result, f'Сумма от {start} до {end}' )
    except Exception as e:
        logger.error(f"Ошибка при вычислении суммы: {str(e)}")
        # Передаёт исключение дальше, чтобы оно было обработано вызывающим кодом.
        raise


# --- Эндпоинты ---

@router.post('/factorial')
async def start_factorial_computation(
    n: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool)
):
    """Запускает вычисление факториала в фоновом режиме."""
    if n <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Число должно быть положительным')
    
    username = current_user['username']
    # Передаем пул в фоновую задачу как обычный аргумент
    background_tasks.add_task(compute_factorial_task, pool, n, username, background_tasks)
    return {'message': f'Вычисление факториала {n} начато в фоне'}

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
