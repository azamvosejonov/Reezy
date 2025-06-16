from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
import requests
import json
import os
from datetime import datetime, timedelta

from models import User
from models.social_account import SocialAccount
from database import get_db
from jose import jwt
from passlib.context import CryptContext

router = APIRouter(tags=["Social Authentication"])

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 Configurations
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID", "")
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET", "")

# OAuth2 URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO = "https://www.googleapis.com/oauth2/v3/userinfo"
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_INFO = "https://api.github.com/user"
FACEBOOK_AUTH_URL = "https://www.facebook.com/v12.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/v12.0/oauth/access_token"
FACEBOOK_USER_INFO = "https://graph.facebook.com/me"

# Redirect URI (should match the one set in your OAuth app settings)
REDIRECT_URI = "http://localhost:8000/auth/callback/{provider}"

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_or_create_user(db: Session, email: str, username: str, provider: str, provider_id: str):
    # Check if social account exists
    social_account = db.query(SocialAccount).filter_by(
        provider=provider,
        provider_id=provider_id
    ).first()
    
    if social_account:
        return social_account.user
    
    # Check if user exists by email
    user = db.query(User).filter_by(email=email).first()
    
    if not user:
        # Create new user
        user = User(
            username=username,
            email=email,
            is_verified=True,
            password=pwd_context.hash(os.urandom(24).hex())  # Random password
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Create social account
    social_account = SocialAccount(
        user_id=user.id,
        provider=provider,
        provider_id=provider_id
    )
    db.add(social_account)
    db.commit()
    
    return user

@router.get("/auth/{provider}")
async def social_auth(provider: str):
    if provider == "google":
        auth_url = f"{GOOGLE_AUTH_URL}?client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI.format(provider=provider)}&response_type=code&scope=openid%20profile%20email"
    elif provider == "github":
        auth_url = f"{GITHUB_AUTH_URL}?client_id={GITHUB_CLIENT_ID}&redirect_uri={REDIRECT_URI.format(provider=provider)}&scope=user:email"
    elif provider == "facebook":
        auth_url = f"{FACEBOOK_AUTH_URL}?client_id={FACEBOOK_CLIENT_ID}&redirect_uri={REDIRECT_URI.format(provider=provider)}&scope=email,public_profile"
    else:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    return {"auth_url": auth_url}

@router.get("/auth/callback/{provider}")
async def social_auth_callback(provider: str, code: str, db: Session = Depends(get_db)):
    try:
        if provider == "google":
            # Exchange code for access token
            token_data = {
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI.format(provider=provider),
                "grant_type": "authorization_code"
            }
            response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
            access_token = response.json().get("access_token")
            
            # Get user info
            user_info = requests.get(
                GOOGLE_USER_INFO,
                headers={"Authorization": f"Bearer {access_token}"}
            ).json()
            
            email = user_info.get("email")
            username = user_info.get("name", "").replace(" ", "").lower() or email.split("@")[0]
            provider_id = user_info.get("sub")
            
        elif provider == "github":
            # Exchange code for access token
            token_data = {
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code
            }
            headers = {"Accept": "application/json"}
            response = requests.post(GITHUB_TOKEN_URL, data=token_data, headers=headers)
            access_token = response.json().get("access_token")
            
            # Get user info
            user_info = requests.get(
                GITHUB_USER_INFO,
                headers={"Authorization": f"token {access_token}"}
            ).json()
            
            # Get primary email if available
            emails = requests.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {access_token}"}
            ).json()
            
            primary_email = next((email["email"] for email in emails if email["primary"] and email["verified"]), None)
            if not primary_email:
                raise HTTPException(status_code=400, detail="No verified email found")
                
            email = primary_email
            username = user_info.get("login")
            provider_id = str(user_info.get("id"))
            
        elif provider == "facebook":
            # Exchange code for access token
            token_data = {
                "client_id": FACEBOOK_CLIENT_ID,
                "client_secret": FACEBOOK_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI.format(provider=provider),
                "code": code
            }
            response = requests.get(FACEBOOK_TOKEN_URL, params=token_data)
            access_token = response.json().get("access_token")
            
            # Get user info
            user_info = requests.get(
                f"{FACEBOOK_USER_INFO}?fields=id,name,email",
                params={"access_token": access_token}
            ).json()
            
            email = user_info.get("email")
            if not email:
                raise HTTPException(status_code=400, detail="Email permission not granted")
                
            username = user_info.get("name", "").replace(" ", "").lower() or email.split("@")[0]
            provider_id = user_info.get("id")
            
        else:
            raise HTTPException(status_code=400, detail="Invalid provider")
        
        # Get or create user
        user = get_or_create_user(db, email, username, provider, provider_id)
        
        # Generate JWT token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        
        # Redirect to frontend with token
        return RedirectResponse(
            url=f"http://localhost:3000/auth/callback?token={access_token}",  # Update with your frontend URL
            status_code=status.HTTP_302_FOUND
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
