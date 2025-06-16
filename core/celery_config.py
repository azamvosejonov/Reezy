import os
from datetime import timedelta
from celery.schedules import crontab

from config import settings

# Broker and result backend settings
broker_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
result_backend = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB + 1}"

# Task settings
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = settings.TIMEZONE
enable_utc = True

# Task result settings
result_expires = timedelta(days=1)
result_persistent = True

# Worker settings
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 100
worker_hijack_root_logger = False

# Beat settings (for scheduled tasks)
beat_schedule = {
    'cleanup-old-posts': {
        'task': 'app.tasks.post_tasks.cleanup_old_posts',
        'schedule': crontab(hour=3, minute=30),  # Run daily at 3:30 AM
        'args': (30,),  # Keep posts for 30 days
    },
    'generate-daily-stats': {
        'task': 'app.tasks.analytics_tasks.generate_daily_stats',
        'schedule': crontab(hour=4, minute=0),  # Run daily at 4:00 AM
    },
}

# Task routes
task_routes = {
    'app.tasks.post_tasks.*': {'queue': 'posts'},
    'app.tasks.media_tasks.*': {'queue': 'media'},
    'app.tasks.notification_tasks.*': {'queue': 'notifications'},
    'app.tasks.analytics_tasks.*': {'queue': 'analytics'},
}

# Task time limits
task_time_limit = 300  # 5 minutes
task_soft_time_limit = 270  # 4.5 minutes

# Task compression
task_compression = 'gzip'

# Task acks late to help with idempotency
task_acks_late = True

# Task reject on worker lost
task_reject_on_worker_lost = True

# Task track started
task_track_started = True

# Worker settings
worker_max_memory_per_child = 120000  # 120MB

# Redis settings
broker_transport_options = {
    'visibility_timeout': 1800,  # 30 minutes
    'fanout_prefix': True,
    'fanout_patterns': True,
}

# Task default queue
task_default_queue = 'default'

# Task default exchange
task_default_exchange = 'tasks'
task_default_exchange_type = 'direct'
task_default_routing_key = 'task.default'
