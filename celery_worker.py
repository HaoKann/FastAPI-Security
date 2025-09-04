import eventlet

# ВАЖНО: Эта команда должна быть В САМОМ НАЧАЛЕ, до всех остальных импортов.
# Она "патчит" стандартные библиотеки Python, чтобы они работали с eventlet.
eventlet.monkey_patch()

from celery import Celery
import os
from dotenv import load_dotenv

# Загружаем переменные окружения ПЕРЕД тем, как их использовать.
# Это гарантирует, что os.getenv() найдет REDIS_URL из .env файла.
load_dotenv()


# --- Настройка Celery ---


# Получаем URL для Redis из переменных окружения.
# Если переменной нет, используется стандартный локальный URL.
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')



# Создаем главный экземпляр Celery
# 'tasks' - это просто имя вашего проекта задач, может быть любым.
# broker - указывает, что Redis будет нашим "диспетчером" (место, куда кладутся задачи).
# backend - также указывает, что Redis будет хранить результаты задач (если они нам понадобятся).
# include - САМЫЙ ВАЖНЫЙ ПАРАМЕТР: список модулей, где Celery должен искать файлы с задачами.
celery_app = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['bg_tasks'] # Указываем, что наши задачи находятся в файле bg_tasks.py
)

# Опциональная конфигурация для улучшения работы
celery_app.conf.update(
    task_track_started=True, # Отслеживать, когда задача началась
    task_serializer='json',
    accept_content=['json'], 
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)