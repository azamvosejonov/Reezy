# Reezy FastAPI Instagram Clone

Bu loyiha Django asosidagi Instagram klonining FastAPI versiyasidir. Asosiy imkoniyatlar: foydalanuvchi ro'yxatdan o'tkazish, profil, postlar, kommentlar va bildirishnomalar.

## Loyihaning tuzilmasi

```
Reezy/
├── main.py                  # FastAPI ilovasi
├── database.py              # SQLAlchemy bazaga ulanish
├── models.py                # SQLAlchemy modellar
├── schemas.py               # Pydantic schemas
├── config.py                # Sozlamalar (BaseSettings)
├── requirements.txt         # Kerakli kutubxonalar
├── routers/
│   ├── __init__.py
│   ├── accounts.py          # Foydalanuvchi endpointlari
│   ├── posts.py             # Post va komment endpointlari
│   └── notifications.py     # Bildirishnomalar endpointi
└── tests/
    └── test_main.py         # Testlar
```

## O'rnatish

1. **Kodni yuklab oling yoki klon qiling:**
   
   ```bash
   cd /home/kali/Desktop/yaratilgan_narsalar/Reezy/
   ```

2. **Virtual environment yarating va faollashtiring (ixtiyoriy, tavsiya etiladi):**
   
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Kerakli kutubxonalarni o'rnating:**
   
   ```bash
   pip install -r requirements.txt
   # yoki xatolik bo'lsa:
   pip install email-validator
   ```

4. **Bazani yaratish (birinchi ishga tushirishda):**
   
   ```python
   # Python interaktiv rejimida yoki alohida faylda
   from database import Base, engine
   Base.metadata.create_all(bind=engine)
   ```

5. **Serverni ishga tushiring:**
   
   ```bash
   uvicorn main:app --reload
   ```

6. **API hujjatlari:**
   
   - Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - Redoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

7. **Testlarni ishga tushirish:**
   
   ```bash
   pytest
   ```

## Muhim endpointlar

- `POST /accounts/register` – Foydalanuvchi ro'yxatdan o'tkazish
- `GET /accounts/profile/{user_id}` – Profil ma'lumotlari
- `POST /posts/` – Post yaratish
- `GET /posts/` – Barcha postlar
- `POST /posts/{post_id}/comment` – Komment qo'shish
- `GET /notifications/` – Bildirishnomalar ro'yxati

## Eslatma
- EmailStr uchun `email-validator` kutubxonasi kerak.
- Avtorizatsiya va autentifikatsiya soddalashtirilgan (JWT yoki OAuth2 qo'shish mumkin).
- Django admin paneli yo'q, lekin SQLAlchemy orqali ma'lumotlar bilan ishlash mumkin.

## Muallif
- Avtomatik migratsiya: Refact Agent
- Asosiy kod: Django loyihasidan FastAPI'ga ko'chirilgan
