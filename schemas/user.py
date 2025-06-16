from datetime import datetime, timedelta
from typing import Optional, List, Union, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator, HttpUrl

from core.security import get_password_hash


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str
    expires_in: int = Field(default=3600, description="Token expiration time in seconds")
    refresh_token: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    email: EmailStr
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class VerifyCodeRequest(BaseModel):
    """Schema for verification code request."""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r'^\d{6}$')
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "code": "123456"
            }
        }


class NewPasswordRequest(BaseModel):
    """Schema for setting a new password."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "reset_token_here",
                "new_password": "NewSecurePassword123"
            }
        }


class UserBase(BaseModel):
    """Base schema for user data."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    profile_picture: Optional[str] = None
    is_private: bool = False
    
class UserWithEmail(UserBase):
    """Base schema for user data that includes email."""
    email: EmailStr

class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, max_length=100)
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return get_password_hash(v)

class UserUpdate(BaseModel):
    """Schema for updating user data."""
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    profile_picture: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    
    @validator('password', pre=True, always=True)
    def hash_password(cls, v):
        if v:
            return get_password_hash(v)
        return v

class UserResponse(UserWithEmail):
    """Schema for user data in responses (includes email)."""
    id: int
    is_verified: bool = False
    created_at: datetime
    
    model_config = {"from_attributes": True}

class PublicUserResponse(UserBase):
    """Schema for public user data (no email)."""
    id: int
    is_verified: bool = False
    created_at: datetime
    
    model_config = {"from_attributes": True}

class UserInDB(UserBase):
    """Schema for user data in the database."""
    id: int
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    model_config = {"from_attributes": True}

class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str

# Token class is now replaced by TokenResponse

class TokenData(BaseModel):
    """Schema for token data."""
    username: Optional[str] = None
    user_id: Optional[int] = None


class PasswordUpdateRequest(BaseModel):
    """Schema for password update request."""
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v
