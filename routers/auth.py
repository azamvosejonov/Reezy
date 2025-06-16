import json
import random
import string
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from fastapi import Depends, HTTPException, status, APIRouter, Form, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from h11._abnf import status_code
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from utils.geoip import GeoIPService, logger
import asyncio

import schemas, models
from models import User, PasswordResetToken
from schemas.user import PasswordUpdateRequest, NewPasswordRequest, VerifyCodeRequest, PasswordResetRequest, \
    TokenResponse
from database import SessionLocal


router = APIRouter(tags=["Authentication"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a password hash"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# This one returns None if token is not present, for optional authentication
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from the JWT token.
    
    Args:
        token: JWT token from the Authorization header
        db: Database session
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If token is invalid, expired, or doesn't match current session
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "Token kiritilmagan"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Decode and verify the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "message": "Yaroqsiz token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except jwt.ExpiredSignatureError:
        # Token has expired - clear it from user's record
        try:
            # Get the user ID from the expired token
            expired_payload = jwt.decode(
                token, 
                SECRET_KEY, 
                algorithms=[ALGORITHM],
                options={"verify_exp": False}
            )
            expired_user_id = expired_payload.get("sub")
            if expired_user_id:
                # Clear the expired token from user's record
                expired_user = db.query(User).filter(User.id == expired_user_id).first()
                if expired_user and expired_user.current_token == token:
                    expired_user.current_token = None
                    db.commit()
        except Exception as e:
            print(f"Error clearing expired token: {e}")
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "Sessiya muddati tugagan. Iltimos, qaytadan kiring"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": f"Yaroqsiz token: {str(e)}"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Yaroqsiz foydalanuvchi ID formati"},
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "message": "Foydalanuvchi topilmadi"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "message": "Ushbu hisob faol emas"},
        )
    
    # Check if the token matches the current active token
    if not user.current_token or user.current_token != token:
        # Clear any invalid token
        if user.current_token:
            user.current_token = None
            db.commit()
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False, 
                "message": "Ushbu seans yangi tizimga kirish tufayli tugatildi",
                "code": "SESSION_TERMINATED"
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_optional_current_user(
    token: str = Depends(optional_oauth2_scheme), 
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.
    
    This is a permissive version of get_current_user that doesn't raise exceptions
    for unauthenticated or invalid tokens. Used for endpoints that work both for
    authenticated and unauthenticated users.
    
    Args:
        token: Optional JWT token from the Authorization header
        db: Database session
        
    Returns:
        Optional[User]: The authenticated user if token is valid, None otherwise
    """
    if not token:
        return None
    
    try:
        # Try to get the user using the main function
        return await get_current_user(token, db)
    except HTTPException:
        # If any HTTP exception occurs (invalid token, expired, etc.), return None
        return None
    except Exception as e:
        # Log unexpected errors but still return None to maintain the optional nature
        print(f"Unexpected error in get_optional_current_user: {e}")
        return None

# JWT Configuration
SECRET_KEY = "supersecret"  # Move to environment variable in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
RESET_TOKEN_EXPIRE_MINUTES = 30  # 30 minutes for reset token

# Email configuration
SMTP_ENABLED = False
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "your-email@gmail.com"
EMAIL_PASSWORD = "your-email-password"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Captcha
captcha_store = {}

def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def verify_captcha(code: str):
    return captcha_store.get("code") == code

@router.get("/captcha")
def get_captcha():
    code = generate_captcha()
    captcha_store["code"] = code
    return {"code": code}

class RegisterForm:
    def __init__(
        self,
        request: Request,
        username: str = Form(..., description="Foydalanuvchi nomi (3-50 belgi, faqat harf, raqam, nuqta va pastki chiziq)"),
        email: str = Form(..., description="Elektron pochta manzili"),
        password: str = Form(..., min_length=8, description="Parol (kamida 8 ta belgi)"),
        captcha: str = Form(..., description="Captcha kodi")
    ):
        self.request = request
        self.username = username
        self.email = email
        self.password = password
        self.captcha = captcha

@router.post(
    "/register", 
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ro'yxatdan o'tish",
    description="Yangi foydalanuvchi ro'yxatdan o'tkazish",
    response_description="Muvaffaqiyatli ro'yxatdan o'tganda access token qaytariladi",
    responses={
        201: {"description": "Foydalanuvchi muvaffaqiyatli ro'yxatdan o'tkazildi"},
        400: {"description": "Noto'g'ri so'rov yoki foydalanuvchi allaqachon mavjud"},
        500: {"description": "Server xatosi"}
    }
)
async def register(
    form_data: RegisterForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Yangi foydalanuvchini ro'yxatdan o'tkazish va avtomatik tizimga kirish.
    
    Muvaffaqiyatli ro'yxatdan o'tganda avtomatik ravishda tizimga kiritiladi
    va JWT token qaytariladi.
    """
    if not verify_captcha(form_data.captcha):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Noto'g'ri captcha kodi"}
        )
    
    # Check if user exists by querying only the ID to avoid missing column errors
    existing_user = db.query(User.id).filter(
        (User.username == form_data.username) | (User.email == form_data.email)
    ).first()
    
    if existing_user is not None:
        # Check which field caused the conflict
        existing = db.query(User).filter(
            (User.username == form_data.username) | (User.email == form_data.email)
        ).first()
        
        if existing.username == form_data.username:
            error_msg = "Bu foydalanuvchi nomi allaqachon band qilingan"
        else:
            error_msg = "Bu elektron pochta manzili allaqachon ro'yxatdan o'tgan"
            
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": error_msg}
        )
    
    hashed_password = get_password_hash(form_data.password)
    
    new_user = User(
        username=form_data.username,
        email=form_data.email,
        hashed_password=hashed_password,
        full_name=form_data.username,
        bio="",
        website="",
        profile_picture="static/images/users/default.png",
        is_private=False,
        is_active=True,
        is_admin=False,
        last_login=datetime.utcnow()
    )
    
    # Get client IP and location
    try:
        client_ip = GeoIPService.get_client_ip(form_data.request)
        location_info = await GeoIPService.get_location_from_ip(client_ip)
        
        # Update user with location info
        new_user.registration_ip = client_ip
        new_user.last_ip = client_ip
        new_user.country = location_info.get('country')
        new_user.region = location_info.get('region')
        new_user.city = location_info.get('city')
        new_user.latitude = location_info.get('latitude')
        new_user.longitude = location_info.get('longitude')
        new_user.timezone = location_info.get('timezone')
    except Exception as e:
        # Log the error but don't fail registration
        logger.error(f"Error getting location info: {str(e)}")
    
    # Create the user in the database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
        
    try:
        # Generate access token for auto-login
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(new_user.id), "username": new_user.username},
            expires_delta=access_token_expires
        )
        
        # Update user's current token and last login
        new_user.current_token = access_token
        new_user.last_login = datetime.utcnow()
        db.commit()
        
        # Refresh the user object to get updated data
        db.refresh(new_user)
        
        # Create default settings for the new user
        try:
            # If you have a UserSettings model, uncomment and modify this section
            # default_settings = models.UserSettings(
            #     user_id=new_user.id,
            #     # Add any default settings here
            # )
            # db.add(default_settings)
            # db.commit()
            pass
        except Exception as settings_error:
            db.rollback()
            print(f"Warning: Could not create default settings: {str(settings_error)}")
            # Continue even if settings creation fails
        

            # Create response data that matches TokenResponse model
            response_data = {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": int(access_token_expires.total_seconds()),
                "refresh_token": None  # Optional field in TokenResponse
            }
            
            # Create response object with the token data
            response = Response(
                content=json.dumps(response_data),
                media_type="application/json",
                status_code=status.HTTP_201_CREATED
            )
            
            # Set headers for Swagger UI auto-authorization
            response.headers["access-token"] = access_token
            response.headers["token-type"] = "bearer"
            response.headers["Authorization"] = f"Bearer {access_token}"
            
            return response_data
                
    except Exception as e:
        db.rollback()
        error_detail = str(e)
        print(f"Registration error: {error_detail}")
        
        # Check for common database errors
        if "UNIQUE constraint failed" in error_detail:
            if "users.username" in error_detail:
                error_msg = "Bu foydalanuvchi nomi allaqachon band qilingan"
            elif "users.email" in error_detail:
                error_msg = "Bu elektron pochta manzili allaqachon ro'yxatdan o'tgan"
            else:
                error_msg = "Ushbu ma'lumotlar bilan foydalanuvchi allaqachon mavjud"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": error_msg}
            )
        
        # For other database errors
        if "no such table" in error_detail.lower():
            error_msg = "Database table not found. Please run database migrations."
        else:
            error_msg = "Ro'yxatdan o'tishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": error_msg}
        )

def generate_reset_code() -> str:
    """Generate a random 8-digit code"""
    return ''.join(random.choices(string.digits, k=8))

@router.post(
    "/logout", 
    response_model=dict, 
    summary="Tizimdan chiqish",
    description="Joriy foydalanuvchi uchun sessiyani tugatish",
    responses={
        200: {"description": "Muvaffaqiyatli chiqish"},
        401: {"description": "Avtorizatsiyadan o'tilmagan"}
    }
)
async def logout(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Joriy foydalanuvchi uchun sessiyani tugatish.
    
    Ushbu amal foydalanuvchining joriy tokenini o'chiradi va uni tizimdan chiqaradi.
    Keyingi kirish uchun qaytadan autentifikatsiyadan o'tish talab qilinadi.
    """
    # Get the token from the Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {
            "success": False,
            "message": "Token kiritilmagan",
            "logged_out": False
        }
    
    token = auth_header.split(" ")[1]
    
    try:
        # Manually decode the token to get the user ID
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        if not user_id:
            return {
                "success": False,
                "message": "Yaroqsiz token",
                "logged_out": False
            }
            
        # Get the user from the database
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            return {
                "success": False,
                "message": "Foydalanuvchi topilmadi",
                "logged_out": False
            }
            
        # Check if the token matches the current token
        if user.current_token != token:
            return {
                "success": False,
                "message": "Yaroqsiz token",
                "logged_out": False
            }
            
        # Clear the current token
        was_logged_in = bool(user.current_token)
        user.current_token = None
        db.commit()
        
        if was_logged_in:
            return {
                "success": True, 
                "message": "Siz muvaffaqiyatli tizimdan chiqdingiz",
                "logged_out": True
            }
            
        return {
            "success": True, 
            "message": "Siz allaqachon tizimdan chiqib bo'lgansiz",
            "logged_out": False
        }
        
    except jwt.ExpiredSignatureError:
        # If token is expired, still allow logout
        try:
            # Get the user ID from the expired token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user and user.current_token == token:
                    user.current_token = None
                    db.commit()
                    return {
                        "success": True,
                        "message": "Sessiya muddati tugaganligi sabab tizimdan chiqarildi",
                        "logged_out": True
                    }
        except Exception:
            pass
            
    except JWTError as e:
        print(f"JWT Error during logout: {str(e)}")
        
    return {
        "success": False,
        "message": "Tizimdan chiqishda xatolik yuz berdi",
        "logged_out": False
    }

class LoginForm:
    def __init__(
        self,
        username: str = Form(..., description="Foydalanuvchi nomi"),
        password: str = Form(..., description="Parol"),
        captcha: str = Form(..., description="Captcha kodi")
    ):
        self.username = username
        self.password = password
        self.captcha = captcha

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Tizimga kirish",
    description="Foydalanuvchi nomi, parol va captcha orqali tizimga kiring",
    response_description="Kirish muvaffaqiyatli bo'lganda access token qaytariladi",
    responses={
        200: {"description": "Muvaffaqiyatli kirish"},
        400: {"description": "Noto'g'ri so'rov"},
        401: {"description": "Kirish rad etildi"},
        403: {"description": "Akkaunt boshqa qurilmada ochiq"}
    }
)
async def login_for_access_token(
    form_data: LoginForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Foydalanuvchi tizimga kirishi uchun endpoint.
    
    Agar foydalanuvchi boshqa qurilmada kirgan bo'lsa, xatolik qaytaradi.
    Muvaffaqiyatli kirishda JWT token qaytariladi.
    """
    if not verify_captcha(form_data.captcha):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Noto'g'ri captcha kodi"}
        )

    # Get the full user object to check for existing sessions
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "Noto'g'ri foydalanuvchi nomi yoki parol"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is already logged in from another device
    if user.current_token:
        try:
            # Verify if the token is still valid
            jwt.decode(user.current_token, SECRET_KEY, algorithms=[ALGORITHM])
            # If we get here, token is still valid - user is already logged in
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False, 
                    "message": "Siz allaqachon boshqa qurilmadan kirgansiz. Iltimos, avval o'sha yerdan chiqib keling."
                }
            )
        except JWTError:
            # Token is expired or invalid, safe to proceed with new login
            pass
    
    try:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "username": user.username}, 
            expires_delta=access_token_expires
        )
        
        # Update user's current token and last login
        user.current_token = access_token
        user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        # Create response with token in both body and header for Swagger UI
        response_data = {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username,
            "expires_in": int(access_token_expires.total_seconds())
        }
        
        # This format is recognized by Swagger UI for auto-authorization
        response = Response(
            content=json.dumps({
                "access_token": access_token,
                "token_type": "bearer"
            }),
            media_type="application/json"
        )
        
        # Set headers for Swagger UI auto-authorization
        response.headers["access-token"] = access_token
        response.headers["token-type"] = "bearer"
        response.headers["Authorization"] = f"Bearer {access_token}"
        
        return response_data
        
    except Exception as e:
        db.rollback()
        print(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": "Tizimga kirishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."}
        )

def send_reset_email(email: str, code: str):
    """For development: Return the code in response instead of sending email"""
    if SMTP_ENABLED:
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = email
            msg['Subject'] = "Parolni tiklash kodi"

            body = f"""
            <h2>Parolni tiklash so'rovi</h2>
            <p>Parolingizni tiklash uchun quyidagi koddan foydalaning:</p>
            <h1 style="color: #4CAF50; font-size: 24px; text-align: center; padding: 10px; background: #f0f0f0; border-radius: 5px; letter-spacing: 5px;">{code}</h1>
            <p>Bu kod {RESET_TOKEN_EXPIRE_MINUTES} daqiqa davomida amal qiladi.</p>
            </p>Rahmat!</p>
            """

            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
        except Exception as e:
            print(f"Email yuborishda xatolik: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Email yuborishda xatolik yuz berdi"}
            )
    else:
        print(f"[DEBUG] Password reset code for {email}: {code}")

@router.post("/request-reset", summary="Parolni tiklash uchun kod so'raladi")
async def request_password_reset(
    request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Parolni tiklash uchun kod generatsiya qilish va foydalanuvchiga qaytarish
    """
    # Check if user exists with this email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        # For security, don't reveal if email exists or not
        return {
            "success": False,
            "message": "Agar bu email ro'yxatdan o'tgan bo'lsa, parolni tiklash kodi yuboriladi"
        }

    # Generate a reset code
    reset_code = generate_reset_code()
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

    # Create or update reset token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.email == request.email
    ).first()

    if reset_token:
        reset_token.token = reset_code
        reset_token.expires_at = expires_at
        reset_token.used = False
    else:
        reset_token = PasswordResetToken(
            email=request.email,
            token=reset_code,
            expires_at=expires_at
        )
        db.add(reset_token)

    db.commit()

    # For development, return the code in the response
    send_reset_email(request.email, reset_code)

    return {
        "success": True,
        "message": "Parolni tiklash kodi yuborildi",
        "reset_code": reset_code,  # Only for development
        "user_id": user.id  # Return user_id for the next step
    }

@router.post("/verify-code", summary="Kodni tekshirish")
async def verify_reset_code(
    request: VerifyCodeRequest,
    db: Session = Depends(get_db)
):
    """
    Kodni tekshirish va yangi parol o'rnatish uchun token qaytarish
    """
    # Find the reset token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == request.code,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Noto'g'ri yoki muddati o'tgan kod"}
        )

    # Get user by email from the token
    user = db.query(User).filter(User.email == reset_token.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "message": "Foydalanuvchi topilmadi"}
        )

    # Mark token as used
    reset_token.used = True
    db.commit()

    # Generate a short-lived JWT token for password reset
    access_token_expires = timedelta(minutes=15)
    access_token = create_access_token(
        data={"sub": str(user.id), "reset": True},
        expires_delta=access_token_expires
    )

    return {
        "success": True,
        "message": "Kod tasdiqlandi",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id
    }

@router.post("/reset-password/{user_id}", summary="Yangi parol o'rnatish")
async def reset_password(
    user_id: int,
    request: NewPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Yangi parol o'rnatish (Authentication kerak emas)
    """
    # Get the user to update
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "message": "Foydalanuvchi topilmadi"}
        )

    # Update the user's password
    hashed_password = pwd_context.hash(request.new_password)
    user.hashed_password = hashed_password

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Invalidate all existing tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.email == user.email
        ).update({"used": True})
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": "Parolni yangilashda xatolik yuz berdi"}
        )

    return {
        "success": True,
        "message": "Parol muvaffaqiyatli yangilandi"
    }

@router.post("/change-password/{user_id}", status_code=status.HTTP_200_OK)
async def change_password(
    user_id: int,
    request: PasswordUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Parolni o'zgartirish (Authentication kerak emas)
    """
    # Get the user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "message": "Foydalanuvchi topilmadi"}
        )
    
    # Verify old password
    if not pwd_context.verify(request.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Eski parol noto'g'ri"}
        )

    # Hash the new password
    hashed_password = pwd_context.hash(request.new_password)

    # Update user's password
    user.hashed_password = hashed_password

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Invalidate all existing tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.email == user.email
        ).update({"used": True})
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": "Parolni yangilashda xatolik yuz berdi"}
        )

    return {
        "success": True,
        "message": "Parol muvaffaqiyatli yangilandi"
    }
