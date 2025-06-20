from celery import Celery

app = Celery(
    'tasks',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    include=['tasks']
)

app.conf.beat_schedule = {
    'periodic-task': {
        'task': 'tasks.periodic_task',
        'schedule': 300.0  # 5 minutda bir
    }
}