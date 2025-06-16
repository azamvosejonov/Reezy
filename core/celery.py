import os
from datetime import timedelta
import logging

from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)

# Only set Django settings module if Django is installed
try:
    import django  # noqa
    # Set the default Django settings module for the 'celery' program if not already set
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.core.settings')
except ImportError:
    # Django is not installed, remove the environment variable if it was set
    os.environ.pop('DJANGO_SETTINGS_MODULE', None)

class CeleryConfig:
    """Celery configuration."""
    
    # Broker settings
    broker_url = 'redis://localhost:6379/0'
    result_backend = 'redis://localhost:6379/0'
    
    # Serialization
    accept_content = ['json', 'pickle']
    task_serializer = 'pickle'
    result_serializer = 'pickle'
    
    # Task settings
    task_default_queue = 'default'
    task_default_exchange = 'default'
    task_default_routing_key = 'default'
    
    # Worker settings
    worker_prefetch_multiplier = 1
    worker_max_tasks_per_child = 100
    worker_max_memory_per_child = 120000  # 120MB
    
    # Task time limits
    task_time_limit = 300  # 5 minutes
    task_soft_time_limit = 270  # 4.5 minutes
    
    # Task result settings
    result_expires = timedelta(days=1)
    result_persistent = True
    
    # Beat settings
    beat_schedule = {
        'cleanup-old-task-results': {
            'task': 'app.tasks.cleanup.cleanup_old_task_results',
            'schedule': crontab(hour=3, minute=0),  # Run daily at 3 AM
            'options': {'queue': 'periodic'}
        },
        'generate-daily-reports': {
            'task': 'app.tasks.reports.generate_daily_reports',
            'schedule': crontab(hour=4, minute=0),  # Run daily at 4 AM
            'options': {'queue': 'reports'}
        },
    }
    
    # Task routes
    task_routes = {
        'app.tasks.email.*': {'queue': 'emails'},
        'app.tasks.reports.*': {'queue': 'reports'},
        'app.tasks.cleanup.*': {'queue': 'maintenance'},
        'app.tasks.media.*': {'queue': 'media'},
    }


def create_celery_app():
    """Create and configure a new Celery application."""
    # Initialize Celery with the project name
    app = Celery(
        'reezy',
        broker='redis://localhost:6379/0',
        backend='redis://localhost:6379/0',
        include=['app.tasks']
    )
    
    # Load configuration from object
    app.config_from_object(CeleryConfig)
    
    # Auto-discover tasks in all installed apps
    app.autodiscover_tasks(packages=['app'])
    
    # Set up debug task
    @app.task(bind=True, name='debug_task')
    def debug_task(self):
        print(f'Request: {self.request!r}')
    
    return app

# Create the Celery app
celery_app = create_celery_app()

if __name__ == '__main__':
    celery_app.start()
