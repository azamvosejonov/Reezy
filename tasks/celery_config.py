import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# RabbitMQ connection settings
RABBITMQ_USER = os.getenv('RABBITMQ_DEFAULT_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_DEFAULT_PASS', 'guest')
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = os.getenv('RABBITMQ_PORT', '5672')

# Redis connection settings
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_DB = os.getenv('REDIS_DB', '0')

# Celery configuration
class CeleryConfig:
    broker_url = f'amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}//'
    result_backend = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    
    # Task settings
    task_serializer = 'json'
    result_serializer = 'json'
    accept_content = ['json']
    timezone = 'Asia/Tashkent'
    enable_utc = True
    
    # Worker settings
    worker_prefetch_multiplier = 1
    worker_max_tasks_per_child = 100
    worker_max_memory_per_child = 120000  # 120MB
    
    # Task time limits
    task_time_limit = 300  # 5 minutes
    task_soft_time_limit = 240  # 4 minutes
    
    # Beat settings
    beat_schedule = {
        'cleanup_old_tasks': {
            'task': 'app.tasks.cleanup.cleanup_old_task_results',
            'schedule': crontab(hour=3, minute=0),  # Run daily at 3 AM
        },
    }

# Initialize Celery
def make_celery():
    celery = Celery('reezy_tasks')
    celery.config_from_object(CeleryConfig, namespace='CELERY')
    
    # Auto-discover tasks
    celery.autodiscover_tasks(['app.tasks'])
    
    return celery

celery_app = make_celery()
