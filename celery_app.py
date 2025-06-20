from celery import Celery
from celery.schedules import crontab
from config import settings
from celery import Celery

# Create Celery app
celery = Celery(
    __name__,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['main_tasks', 'tasks.post_tasks']
)

# Configure Celery
celery.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Tashkent',
    enable_utc=True,
    beat_schedule={
        'update-data-every-30-minutes': {
            'task': 'main_tasks.update_data',
            'schedule': 1800.0,  # 30 minutes
        },
        'cleanup-old-media-every-day': {
            'task': 'tasks.post_tasks.cleanup_old_media',
            'schedule': 86400.0,  # 24 hours
        },
    }
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
        'task': 'main_tasks.update_data',
        'schedule': 3.0,  # Har 3 soniyada
    },
    'cleanup-old-media': {
        'task': 'tasks.post_tasks.cleanup_old_media',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}
