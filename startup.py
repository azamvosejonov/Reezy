from database import Base, engine
import os

def create_tables():
    # Agar eski db.sqlite3 mavjud bo'lsa, uni o'chirib tashlash (faqat test/prototip uchun!)
    if os.path.exists('db.sqlite3'):
        os.remove('db.sqlite3')
    Base.metadata.create_all(bind=engine)

