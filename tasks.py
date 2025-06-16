from celery_app import celery

@celery.task
def update_data():
    # Bu yerga ma'lumotlarni yangilash mantig'ini yozing
    # Masalan, ma'lumotlar bazasidan o'qish, API so'rovlari yuborish va hokazo.
    print("Ma'lumotlar yangilanmoqda...")
    return {"status": "success", "message": "Data updated"}
