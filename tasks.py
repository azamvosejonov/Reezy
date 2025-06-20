from celery import shared_task

@shared_task
def periodic_task():
    print("Periodic task is running...")
    # Add your processing logic here