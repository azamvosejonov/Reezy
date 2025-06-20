from celery_app import celery

@celery.task


@celery.task
def periodic_task():
    print("Periodic task is running...")
    # Add your processing logic here