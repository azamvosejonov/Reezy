from .celery_config import celery_app

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
__all__ = ('celery_app',)

# Import tasks to register them with Celery
from . import post_tasks  # noqa
