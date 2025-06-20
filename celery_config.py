from celery import Celery
from celery.schedules import crontab
import os

# Create Celery app
app = Celery('tasks')

# Configure Celery
app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tashkent',
    enable_utc=True,
    worker_redirect_stdouts_level='INFO',
    beat_schedule={
        'example-periodic-task': {
            'task': 'tasks.example_task',
            'schedule': crontab(minute='*/5'),  # Every 5 minutes
        },
    },
    beat_scheduler='celery.beat.PersistentScheduler',
    beat_schedule_filename='/app/celerybeat-schedule/schedule.db'
)

# Example task (you can customize this)
@app.task
async def example_task():
    print("Running example task")
    return "Task completed successfully"
