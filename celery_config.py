from celery import Celery
import os

# Create Celery app
app = Celery('app',
             broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
             backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'))

# Configure Celery
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tashkent',
    enable_utc=True,
    worker_redirect_stdouts_level='INFO'
)

# Example task
@app.task
def example_task():
    print("Running example task")
    return "Task completed successfully"
