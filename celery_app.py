from celery import Celery
from celery.schedules import crontab
from config import settings

celery = Celery(
    __name__,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['tasks', 'tasks.post_tasks']  # Include tasks from both files
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
    # Add this to ensure the task is recognized
    'cleanup_old_media': {
        'task': 'tasks.cleanup_old_media',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    # Add this to ensure the task is recognized
    'cleanup_old_media': {
        'task': 'tasks.cleanup_old_media',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}
