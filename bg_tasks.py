# tenacity для настройки повторных попыток задач при сбоях.
from tenacity import retry, stop_after_attempt, wait_fixed
# Поддержка асинхронного программирования для не блокирующих операций.
import asyncio
# Модуль Python для записи логов (отладка, ошибки, информация).
import logging


logger = logging.getLogger('main')


# BackgroundTasks позволяет запускать тяжёлые задачи (как факториал) в фоне, не блокируя клиента.
# 1. Фоновые задачи (BackgroundTasks) — для тяжёлых вычислений
# Функция для симуляции тяжёлых вычислений. Это пример задачи, которую можно выполнить в фоне.



# Функция с повторными попытками
# Декоратор, который пытается выполнить функцию до 3 раз с паузой 2 секунды между попытками, если возникает ошибка.
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2)) 
async def compute_factorial_async(db_pool, n: int, username: str):
    try:
        # Записывает начало задачи в лог
        logger.info(f"Начало вычисление факториала {n} для {username}")
        await asyncio.sleep(5) # Асинхронная задержка
        result = 1
        for i in range(1, n + 1):
            result *= i
        async with db_pool.acquire() as conn:
                await conn.execute(
                    'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                    username, f"factorial of {n}", result
                )
        # Записывает успешное завершение.
        logger.info(f"Успешно вычислен факториал {n} = {result}")
        task_id = f"task_{n}_{username}"
        await notify_completion(task_id, username, result, db_pool)
    except Exception as e:
        logger.error(f"Ошибка при вычислении факториала {n}: {str(e)}")
        raise # Передаём ошибку дальше для retry

# Функция compute_sum_range, которая вычисляет сумму чисел в заданном диапазоне асинхронно.
# @retry - декоратор из библиотеки tenacity, который позволяет повторить выполнение функции до 3 раз с интервалом 2 секунды, 
# если она завершится с ошибкой. Это полезно для обработки временных сбоев (например, с базой данных).
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def compute_sum_range(db_pool, start: int, end: int, username: str):
    try:
        logger.info(f"Начало вычисления суммы от {start} до {end} для {username}")
        await asyncio.sleep(3) # Симуляция длительной задачи
        result = sum(range(start, end + 1))
        async with db_pool.acquire() as conn: # Используем acquire для asyncpg
                await conn.execute(
                    'INSERT INTO calculations (username, task, result) VALUES ($1, $2, $3)',
                    username, f"sum from {start} to {end}", result
                )
        logger.info(f"Успешно вычислена сумма от {start} до {end} = {result}")
        task_id = f"task_sum_{start}_{end}_{username}"
        await notify_completion(task_id, username, result)
    except Exception as e:
        logger.error(f"Ошибка при вычислении суммы: {str(e)}")
        # Передаёт исключение дальше, чтобы оно было обработано вызывающим кодом.
        raise


# Добавление уведомлений
# Функцию для отправки уведомлений через WebSocket после завершения compute_factorial_async
async def notify_completion(task_id: str, username: str, result: int):
    await asyncio.sleep(2) # Короткая задержка для симуляции
    from websocket import manager # Импорт здесь, чтобы избежать круговой зависимости
    await manager.broadcast(f"Задача {task_id} для {username} завершена, результат: {result}")