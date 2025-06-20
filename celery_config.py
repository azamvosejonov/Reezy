from celery import Celery

app = Celery(
    'reezy',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
    include=['tasks.post_tasks']
)

# Configure Redis as the scheduler
app.conf.update(
    beat_scheduler='celery.beat:PersistentScheduler'
)

app.conf.beat_schedule = {
    'periodic-task': {
        'task': 'tasks.periodic_task',
        'schedule': 300.0  # 5 minutes
    }
}