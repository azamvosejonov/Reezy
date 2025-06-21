import json
import random
import string
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List, Union
from urllib import request

import bcrypt
from fastapi import Depends, HTTPException, status, APIRouter, Form, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

class LoginRequest(BaseModel):
    username: str = Field(..., description="Foydalanuvchi nomi", example="example_user")
    password: str = Field(..., description="Parol", example="your_password", min_length=8)
    captcha: str = Field(..., description="Captcha kodi", example="123456")

from fastapi import Response

# Swagger UI bilan integratsiya uchun klass
# Define response models first
class UserInfo(BaseModel):
    """User information model for authentication response"""
    id: int
    username: str
    email: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "username": "example_user",
                "email": "user@example.com"
            }
        }

class TokenResponse(BaseModel):
    """Token response model for authentication endpoints."""
    access_token: str
    token_type: str = "bearer"
    scope: str = "api"
    success: bool = True
    message: str
    user: UserInfo

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "scope": "api",
                "success": True,
                "message": "Tizimga kiritildi",
                "user": {
                    "id": 1,
                    "username": "example_user",
                    "email": "user@example.com"
                }
            },
            "description": "Authentication token response",
            "type": "object",
            "properties": {
                "access_token": {"type": "string", "description": "JWT access token"},
                "token_type": {"type": "string", "enum": ["bearer"]},
                "scope": {"type": "string", "description": "Scope of the access"},
                "success": {"type": "boolean", "description": "Indicates if the request was successful"},
                "message": {"type": "string", "description": "Human-readable message"},
                "user": {
                    "$ref": "#/components/schemas/UserInfo"
                }
            },
            "required": ["access_token", "user", "message"]
        }
    )

# Add UserInfo to the OpenAPI schema
UserInfo.Config.schema_extra = {
    "description": "User information",
    "type": "object",
    "properties": {
        "id": {"type": "integer", "format": "int64"},
        "username": {"type": "string"},
        "email": {"type": "string", "format": "email"}
    },
    "required": ["id", "username", "email"]
}

class SwaggerAuthResponse(JSONResponse):
    def __init__(self, content: Dict[str, Any], token: str, status_code: int = 200):
        super().__init__(content, status_code=status_code)
        # Set token in headers for Swagger UI
        self.headers["Authorization"] = f"Bearer {token}"
        self.headers["X-Swagger-UI-Auth-Reset"] = "true"
        # Set token in cookie
        self.set_cookie(
            key="Authorization",
            value=f"Bearer {token}",
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        # Add token to response body
        content["access_token"] = token
        content["token_type"] = "bearer"
        # Swagger UI integration
        self.headers["X-Swagger-UI-Auth-Token"] = token
        self.headers["X-Swagger-UI-Auth-Status"] = "active"
        self.headers["X-Swagger-UI-Auth-Type"] = "bearer"
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from models.base_models import UserSettings
from services.ip_service import IPService
import asyncio

from utils.geoip import GeoIPService
import logging

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize IP service
ip_service = IPService()

import schemas, models
from models import User, PasswordResetToken
from schemas.user import PasswordUpdateRequest, NewPasswordRequest, VerifyCodeRequest, PasswordResetRequest, \
    TokenResponse, UserResponse
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

class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    async def __call__(self, request: Request = None) -> Optional[str]:
        # First try to get token from Authorization header
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            return authorization.split(" ")[1]
            
        # Then try to get token from cookie
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            return token.split(" ")[1]
            
        # If auto_error is True and no token, raise error
        if self.auto_error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearerWithCookie(
    tokenUrl="/api/v1/auth/token",
    scopes={"api": "Access to the API endpoints"},
    auto_error=True
)

# Optional OAuth2 scheme for endpoints that work with or without authentication
optional_oauth2_scheme = OAuth2PasswordBearerWithCookie(
    tokenUrl="/api/v1/auth/token",
    auto_error=False,
    scopes={"api": "Access to the API endpoints"}
)

# JWT Configuration
# Note: In production, use environment variables for these values
SECRET_KEY = "supersecret"  # Must match the key used in token creation
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days in minutes
TOKEN_URL = "/api/v1/auth/token"  # Full path to token endpoint
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

# This one returns None if token is not present, for optional authentication
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

async def get_current_user(
    request: Request,
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
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"success": False, "message": "Avtorizatsiya talab qilinadi"},
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try to get token from Authorization header if not provided
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            # Try to get token from cookie
            token = request.cookies.get("access_token")
            if token and token.startswith("Bearer "):
                token = token.split(" ")[1]
    
    if not token:
        raise credentials_exception
    
    try:
        # Decode and verify the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
            
        # Get user from database
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            raise credentials_exception
            
        # Verify token matches user's current token
        if user.current_token != token:
            raise credentials_exception
            
        return user
        
    except jwt.ExpiredSignatureError:
        # Handle expired token
        try:
            # Try to get username from expired token
            expired_payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={"verify_exp": False}
            )
            username = expired_payload.get("sub")
            if username:
                # Clear the expired token from user's record
                user = db.query(User).filter(User.username == username).first()
                if user and user.current_token == token:
                    user.current_token = None
                    db.commit()
        except Exception:
            pass
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "Token muddati tugagan"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": f"Yaroqsiz token: {str(e)}"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": f"Server xatosi: {str(e)}"}
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

# OAuth2 Configuration for Swagger UI
oauth2_scheme = OAuth2PasswordBearerWithCookie(
    tokenUrl="/api/v1/auth/token",
    scopes={"api": "Full access to API"}
)
TOKEN_URL = "/api/v1/auth/token"  # Full path to token endpoint
RESET_TOKEN_EXPIRE_MINUTES = 30  # 30 minutes for reset token

# Email configuration
SMTP_ENABLED = False
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "your-email@gmail.com"
EMAIL_PASSWORD = "your-email-password"

# Password hashing
def generate_captcha():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_reset_code():
    return str(random.randint(100000, 999999))

def generate_temp_password():
    """Generate a temporary password with letters and numbers"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(12))

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
    status_code=status.HTTP_201_CREATED)
async def register(
    form_data: RegisterForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Yangi foydalanuvchi ro'yxatdan o'tkazish.
    
    Muvaffaqiyatli ro'yxatdan o'tganda avtomatik ravishda tizimga kiritiladi
    va JWT token qaytariladi.
    """
    # Validate captcha
    if not verify_captcha(form_data.captcha):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Noto'g'ri captcha kodi"}
        )
    
    # Check if username already exists
    existing_user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.email)
    ).first()
    
    if existing_user:
        conflict_field = "username" if existing_user.username == form_data.username else "email"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"success": False, "message": f"Bunday {conflict_field} allaqachon mavjud"}
        )
    
    # Hash the password
    hashed_password = get_password_hash(form_data.password)
    
    # Create new user
    new_user = User(
        username=form_data.username,
        email=form_data.email,
        hashed_password=hashed_password,
        is_active=True,
        is_verified=False,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow()
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Generate JWT token with 30 days expiration
    access_token_expires = timedelta(days=30)
    access_token = create_access_token(
        data={
            "sub": str(new_user.id),
            "username": new_user.username,
            "email": new_user.email,
            "scopes": ["api"],
            "is_admin": False
        },
        expires_delta=access_token_expires
    )
    
    # Update user with current token
    new_user.current_token = access_token
    db.commit()
    
    # Create the response data using TokenResponse model
    response_data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        scope="api",
        success=True,
        message="Muvaffaqiyatli ro'yxatdan o'tdingiz",
        user=UserInfo(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email
        )
    )
    
    # Create the response with proper headers for Swagger UI
    response = JSONResponse(
        content=response_data.model_dump(),
        status_code=status.HTTP_201_CREATED,
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Swagger-UI-Auth-Reset": "true",
            "X-Swagger-UI-Auth-Token": access_token,
            "X-Swagger-UI-Auth-Status": "active",
            "X-Swagger-UI-Auth-Type": "bearer"
        }
    )
    
    # Set the access token in an HTTP-only cookie for web clients
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,  # 30 days in seconds
        path="/"
    )
    
    return response



def generate_reset_code() -> str:
    """Generate a random 8-digit code"""
    return ''.join(random.choices(string.digits, k=8))

@router.post(
    "/logout", 
    response_model=dict, 
    summary="Logout user",
    description="Invalidate the current user's authentication token")
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Joriy foydalanuvchi uchun sessiyani tugatish.
    
    Ushbu amal foydalanuvchining joriy tokenini o'chiradi va uni tizimdan chiqaradi.
    Keyingi kirish uchun qaytadan autentifikatsiyadan o'tish talab qilinadi.
    """
    try:
        token = None
        
        # Try to get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        
        # If no token in header, try to get from cookies
        if not token and "access_token" in request.cookies:
            cookie_token = request.cookies.get("access_token")
            if cookie_token and cookie_token.startswith("Bearer "):
                token = cookie_token.split(" ")[1]
        
        if not token:
            return {
                "success": False,
                "message": "Token topilmadi. Siz avtorizatsiyadan o'tmagansiz.",
                "logged_out": False
            }
        
        # Verify the token is valid and get the username
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            
            # Compare usernames
            if not username or username != current_user.username:
                return {
                    "success": False,
                    "message": "Yaroqsiz token. Iltimos, qaytadan kiring.",
                    "logged_out": False
                }
        except JWTError:
            # If token is invalid, still proceed with logout
            pass
        
        # Clear the current token in the database
        current_user.current_token = None
        db.commit()
        
        # Create response with success message
        response_data = {
            "success": True,
            "message": "Siz muvaffaqiyatli tizimdan chiqdingiz",
            "logged_out": True
        }
        
        # Create JSON response
        response = JSONResponse(content=response_data)
        
        # Clear all auth-related cookies
        for cookie_name in ["access_token", "Authorization"]:
            response.delete_cookie(
                key=cookie_name,
                path="/",
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax"
            )
            
        # Clear Swagger UI auth headers
        response.headers["X-Swagger-UI-Auth-Reset"] = "true"
        response.headers["X-Swagger-UI-Auth-Status"] = "inactive"
        response.headers.pop("Authorization", None)
        response.headers.pop("X-Swagger-UI-Auth-Token", None)
        response.headers.pop("X-Swagger-UI-Auth-Type", None)
        
        return response
        
    except jwt.ExpiredSignatureError:
        # If token is expired, still clear the token from the user record
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
            user_id = payload.get("sub")
            
            if user_id and int(user_id) == current_user.id and current_user.current_token == token:
                current_user.current_token = None
                db.commit()
                
                response = JSONResponse(
                    content={
                        "success": True,
                        "message": "Sessiya muddati tugaganligi sabab tizimdan chiqarildi",
                        "logged_out": True
                    },
                    status_code=status.HTTP_200_OK
                )
                
                # Clear cookies and headers
                response.delete_cookie("access_token", path="/", secure=True, httponly=True, samesite="lax")
                response.headers.update({
                    "Authorization": "",
                    "X-Swagger-UI-Auth-Reset": "true",
                    "X-Swagger-UI-Auth-Status": "inactive",
                    "X-Swagger-UI-Auth-Token": ""
                })
                return response
                
        except Exception as e:
            logger.error(f"Error during expired token cleanup: {str(e)}")
            
        # If we get here, the token was expired but we couldn't clear it
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessiya muddati tugagan"
        )
        
    except (JWTError, Exception) as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tizimdan chiqishda xatolik yuz berdi"
        )

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

@router.post("/login", response_model=TokenResponse, summary="User login", description="Authenticate user and return JWT token")
async def login(
    request: Request,
    form_data: LoginForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Foydalanuvchi tizimga kirishi uchun endpoint.
    
    Muvaffaqiyatli kirishda JWT token qaytariladi.
    """
    try:
        # Verify captcha first
        if not verify_captcha(form_data.captcha):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "message": "Noto'g'ri captcha kodi"}
            )
            
        # Get user by username
        user = db.query(User).filter(User.username == form_data.username).first()
        
        # Verify user exists and password is correct
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"success": False, "message": "Noto'g'ri foydalanuvchi nomi yoki parol"}
            )
            
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"success": False, "message": "Ushbu hisob faol emas"}
            )
            
        # Generate JWT token with 30 days expiration
        access_token_expires = timedelta(days=30)
        access_token = create_access_token(
            data={
                "sub": user.username,
                "scopes": ["api"],
                "user_id": user.id,
                "email": user.email,
                "is_admin": getattr(user, 'is_admin', False)
            },
            expires_delta=access_token_expires
        )
        
        # Update user's last login and current token
        user.last_login = datetime.utcnow()
        user.current_token = access_token
        db.commit()
        db.refresh(user)
        
        # Create response data
        response_data = {
            "access_token": access_token,
            "token_type": "bearer",
            "scope": "api",
            "success": True,
            "message": "Tizimga muvaffaqiyatli kiritildi",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": getattr(user, 'full_name', ''),
                "profile_picture": getattr(user, 'profile_picture', ''),
                "is_admin": getattr(user, 'is_admin', False),
                "is_active": user.is_active
            }
        }
        
        # Create response with token in both body and headers
        response = JSONResponse(content=response_data)
        
        # Set token in header for Swagger UI and API clients
        response.headers["Authorization"] = f"Bearer {access_token}"
        response.headers["Access-Control-Expose-Headers"] = "Authorization"
        
        # Add Swagger UI specific headers
        response.headers["X-Swagger-UI-Auth-Token"] = access_token
        response.headers["X-Swagger-UI-Auth-Status"] = "active"
        response.headers["X-Swagger-UI-Auth-Type"] = "bearer"
        
        # Set token in cookie for browser-based access
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=30 * 24 * 60 * 60,  # 30 days
            path="/"
        )
        
        # Also set a separate cookie for Swagger UI
        response.set_cookie(
            key="Authorization",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=30 * 24 * 60 * 60,  # 30 days
            path="/"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": "Tizimda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring."}
        )
    return response

@router.post("/password-reset/request", response_model=schemas.BaseResponse, summary="Parolni tiklash kodini so'rab olish", tags=["Password Reset"])
async def request_password_reset(
    request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Parolni tiklash uchun kod so'rab olish
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        return schemas.BaseResponse(
            success=False,
            message="Bu email bilan ro'yxatdan o'tgan foydalanuvchi topilmadi"
        )

    try:
        # Generate reset code
        reset_code = generate_reset_code()
        
        # Generate temporary password
        temp_password = generate_temp_password()
        
        # Update user's password
        user.hashed_password = pwd_context.hash(temp_password)
        
        # Check for existing token
        existing_token = db.query(PasswordResetToken).filter_by(user_id=user.id).first()
        
        if existing_token:
            # Update existing token
            existing_token.token = reset_code
            existing_token.expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
        else:
            # Create new token
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=reset_code,
                expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
            )
            db.add(reset_token)
            
        db.commit()

        # Prepare user profile data
        user_profile = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "bio": user.bio,
            "profile_picture": user.profile_picture,
            "created_at": user.created_at.isoformat(),
            "is_active": user.is_active
        }

        return schemas.BaseResponse(
            success=True,
            message="Parol muvaffaqiyatli yangilandi",
            data={
                "user": user_profile,
                "temp_password": temp_password
            }
        )
    except Exception as e:
        db.rollback()
        return schemas.BaseResponse(
            success=False,
            message="Xatolik yuz berdi: " + str(e)
        )

@router.post("/password-reset/reset", response_model=schemas.Message, summary="Yangi parol o'rnatish", tags=["Password Reset"], include_in_schema=False)
async def reset_password(
    user_id: int,
    request: NewPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
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

@router.post("/password-reset/change", response_model=schemas.Message, summary="Parolni o'zgartirish", tags=["Password Reset"])
async def change_password(
    user_id: int,
    request: PasswordUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
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
