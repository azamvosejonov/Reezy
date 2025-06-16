from celery import Celery
from celery.schedules import crontab
from config import settings

celery = Celery(
    __name__,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['tasks']  # tasks.py faylini avtomatik topish uchun
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Davriy vazifani sozlash
celery.conf.beat_schedule = {
    'update-data-every-3-seconds': {
        'task': 'tasks.update_data',
        'schedule': 3.0,  # Har 3 soniyada
    },
}
