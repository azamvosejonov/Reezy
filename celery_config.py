from celery import Celery

app = Celery(
    'reezy',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    include=['tasks.post_tasks']
)

app.conf.beat_schedule = {
    'periodic-task': {
        'task': 'tasks.periodic_task',
        'schedule': 300.0  # 5 minutes
    }
}