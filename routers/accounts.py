from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Query, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_, UniqueConstraint
import models
from database import SessionLocal
from schemas.user import UserInDB, UserResponse, PasswordUpdateRequest
from schemas.channel import ChannelInDB
from models.user import User
from core.security import pwd_context, verify_password, get_password_hash
from jose import jwt, JWTError
import random, string, os, shutil, smtplib
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, List, Dict, Any
from fastapi.security import OAuth2PasswordBearer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid

SECRET_KEY = "supersecret"
ALGORITHM = "HS256"
USER_IMAGE_DIR = "media/users/"
os.makedirs(USER_IMAGE_DIR, exist_ok=True)

# Email configuration - Disabled for now
SMTP_ENABLED = False  # Set to False to return codes in response
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "kaxorovorif6@gmail.com"
EMAIL_PASSWORD = "Orifjon360"
RESET_TOKEN_EXPIRE_MINUTES = 30  # 30 minutes for reset token expiration

router = APIRouter(
    prefix="/accounts",
    tags=["accounts"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

from routers.auth import oauth2_scheme, get_password_hash, verify_password, create_access_token, \
    ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user, get_optional_current_user


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def send_password_email(email: str, new_password: str):
    """Send the new password to the user's email"""
    if SMTP_ENABLED:
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = email
            msg['Subject'] = "Sizning yangi parolingiz"  # Your new password
            
            body = f"""
            <h2>Yangi parol</h2>
            <p>Sizning yangi parolingiz:</p>
            <div style="background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <h1 style="color: #4CAF50; font-size: 24px; text-align: center; margin: 0; padding: 10px 0; letter-spacing: 2px;">{new_password}</h1>
            </div>
            <p><strong>Diqqat!</strong> Ushbu parolni xavfsiz joyga saqlang va hech kimga bermang.</p>
            <p>Profil xavfsizligi uchun parolni tez orada o'zgartirishingizni maslahat beramiz.</p>
            <p>Rahmat!</p>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
        except Exception as e:
            print(f"Email yuborishda xatolik: {e}")
            # Don't raise an error, just log it since we'll return the password in the response
    else:
        print(f"[DEBUG] New password for {email}: {new_password}")
        return new_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

class SearchResult(BaseModel):
    users: List[UserResponse]
    channels: List[ChannelInDB]

    model_config = {"from_attributes": True}

@router.get("/search", response_model=SearchResult, summary="Foydalanuvchilar va kanallarni qidirish")
async def search_all(
    q: str = Query(..., min_length=1, description="Qidiruv so'rovi"),
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    # TODO: Add proper authentication
    # current_user: User = Depends(get_current_user)
):
    """
    Foydalanuvchilar va kanallarni qidirish.
    Qidiruv so'rovi bo'yicha foydalanuvchilar va kanallarni qaytaradi.
    Blocklangan foydalanuvchilar natijalarga kiritilmaydi.
    """
    from sqlalchemy.orm import joinedload
    from sqlalchemy import and_, or_, not_
    search = f"%{q}%"
    
    # Temporary hardcoded user ID for testing
    current_user_id = 1
    
    # Get list of blocked users (both directions)
    blocked_users_subq = db.query(models.Block.blocked_id).filter(
        models.Block.blocker_id == current_user_id
    ).union(
        db.query(models.Block.blocker_id).filter(
            models.Block.blocked_id == current_user_id
        )
    ).subquery()
    
    # Foydalanuvchilarni qidirish - faqat kerakli columnlarni tanlab olamiz
    from sqlalchemy.orm import aliased
    from sqlalchemy import select
    
    # First, get the user IDs that match the search and are not blocked
    user_query = db.query(models.User.id).filter(
        or_(
            models.User.username.ilike(search),
            models.User.full_name.ilike(search)
        ),
        models.User.is_active == True,
        ~models.User.id.in_(select(blocked_users_subq))  # Exclude blocked users using select()
    )
    
    # Only show public profiles or private profiles that the user follows
    user_query = user_query.filter(
        (models.User.is_private == False) | 
        (models.User.id.in_(
            db.query(models.Follower.followed_id)
            .filter(models.Follower.follower_id == current_user_id)
        ))
    )
    
    user_ids = [uid[0] for uid in user_query.offset(skip).limit(limit).all()]
    
    # If no users found, initialize empty users list
    user_schemas = []
    if not user_ids:
        return SearchResult(users=[], channels=[])
    
    # Get follower counts for these users
    from sqlalchemy import func
    follower_counts = db.query(
        models.Follower.followed_id,
        func.count(models.Follower.follower_id).label('count')
    ).filter(
        models.Follower.followed_id.in_(user_ids)
    ).group_by(models.Follower.followed_id).all()
    
    followers_map = {user_id: count for user_id, count in follower_counts}
    
    # Get user data with required columns
    users = db.query(
        models.User.id,
        models.User.username,
        models.User.email,
        models.User.full_name,
        models.User.bio,
        models.User.profile_picture,
        models.User.is_verified,
        models.User.created_at
    ).filter(
        models.User.id.in_(user_ids)
    ).all()
    
    # Convert user data to response schemas
    user_schemas = []
    for user in users:
        try:
            user_data = {
                'id': user[0],
                'username': user[1],
                'email': user[2] if user[2] and '@' in str(user[2]) else f"{user[1]}@example.com",
                'full_name': user[3] or "",
                'bio': user[4] or "",
                'profile_picture': user[5] or "",
                'is_verified': user[6] or False,
                'created_at': user[7],
                'followers_count': followers_map.get(user[0], 0)
            }
            user_schemas.append(UserResponse(**user_data))
        except Exception as e:
            # Skip users that can't be properly serialized
            print(f"Skipping user {user[0] if user else 'unknown'} due to validation error: {str(e)}")
            continue
    
    # Kanallarni qidirish - faqat kerakli columnlarni tanlab olamiz
    # First get channel IDs that match the search
    channel_ids = db.query(models.Channel.id).filter(
        or_(
            models.Channel.name.ilike(search),
            models.Channel.description.ilike(search)
        ),
        models.Channel.is_active == True
    ).offset(skip).limit(limit).all()
    
    channel_ids = [cid[0] for cid in channel_ids]
    
    # If no channels found, return users only
    if not channel_ids:
        return SearchResult(users=user_schemas, channels=[])
    
    # Get channel creators
    creator_ids = db.query(models.Channel.creator_id).filter(
        models.Channel.id.in_(channel_ids),
        models.Channel.creator_id.isnot(None)
    ).distinct().all()
    
    creator_ids = [cid[0] for cid in creator_ids]
    
    # Get creator info
    creators_map = {}
    if creator_ids:
        creators = db.query(
            models.User.id,
            models.User.username,
            models.User.profile_picture
        ).filter(
            models.User.id.in_(creator_ids)
        ).all()
        
        creators_map = {
            creator[0]: {
                'id': creator[0],
                'username': creator[1],
                'profile_picture': creator[2]
            } for creator in creators
        }
    
    # Now get the channel data with only the required columns
    channels = db.query(
        models.Channel.id,
        models.Channel.name,
        models.Channel.description,
        models.Channel.image,
        models.Channel.creator_id,
        models.Channel.created_at,
        models.Channel.is_active
    ).filter(
        models.Channel.id.in_(channel_ids)
    ).all()
    
    # Convert SQLAlchemy models to Pydantic models
    user_schemas = [
        UserResponse.model_validate({
            'id': user[0],  # id
            'username': user[1],  # username
            'email': user[2],  # email
            'full_name': user[3],  # full_name
            'bio': user[4],  # bio
            'profile_picture': user[5],  # profile_picture
            'is_verified': user[6],  # is_verified
            'created_at': user[7],  # created_at
            'followers_count': followers_map.get(user[0], 0)  # followers count
        }) for user in users
    ]
    
    channel_schemas = [ChannelInDB.model_validate({
        'id': channel[0],  # id
        'name': channel[1],  # name
        'description': channel[2],  # description
        'image': channel[3],  # image
        'creator_id': channel[4],  # creator_id
        'created_at': channel[5],  # created_at
        'is_active': channel[6],  # is_active
        'creator': creators_map.get(channel[4]) if channel[4] else None  # creator info
    }) for channel in channels]
    
    return SearchResult(users=user_schemas, channels=channel_schemas)

class UserUpdateResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    profile_picture: Optional[str] = None
    is_private: bool = False
    is_verified: bool = False
    created_at: datetime
    
    model_config = {"from_attributes": True}

@router.put(
    "/update", 
    response_model=UserUpdateResponse, 
    summary="Update account information",
    description="""
    Update your account information. 
    - Only provided fields will be updated
    - To remove profile picture, send 'remove_picture=true' as form data
    - To update profile picture, send the new image file
    - Empty strings will be converted to null/None
    """
)
async def update_account(
    db: Session = Depends(get_db),
    full_name: Optional[str] = Form(None, description="Optional full name"),
    bio: Optional[str] = Form(None, description="Optional bio"),
    website: Optional[str] = Form(None, description="Optional website URL"),
    file: UploadFile = File(None),
    remove_picture: Optional[bool] = Form(
        False, 
        description="Set to true to remove existing profile picture"
    ),
):
    # TODO: Add proper authentication
    current_user = db.query(models.User).filter(models.User.id == 1).first()
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update only provided fields
    if full_name is not None:
        current_user.full_name = full_name.strip() if full_name and full_name.strip() else None
    
    if bio is not None:
        current_user.bio = bio.strip() if bio and bio.strip() else None
    
    if website is not None:
        current_user.website = website.strip() if website and website.strip() else None

    # Handle profile picture operations only if explicitly requested
    if remove_picture and current_user.profile_picture:
        # Remove existing profile picture if requested
        try:
            if os.path.exists(current_user.profile_picture):
                os.remove(current_user.profile_picture)
            current_user.profile_picture = None
        except Exception as e:
            print(f"Error removing profile picture: {e}")
    
    # Handle new profile picture upload if provided
    if file and hasattr(file, 'filename') and file.filename:  # Only if file is provided and has a filename
        upload_dir = "static/images/users/"
        os.makedirs(upload_dir, exist_ok=True)

        # Remove old profile picture if exists
        if current_user.profile_picture:
            try:
                if os.path.exists(current_user.profile_picture):
                    os.remove(current_user.profile_picture)
            except Exception as e:
                print(f"Error removing old profile picture: {e}")

        # Save new profile picture
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        current_user.profile_picture = file_path

    try:
        db.commit()
        db.refresh(current_user)
        
        # Create response manually to avoid validation errors
        return {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email if hasattr(current_user, 'email') else None,
            "full_name": current_user.full_name,
            "bio": current_user.bio,
            "website": current_user.website,
            "profile_picture": current_user.profile_picture,
            "is_private": current_user.is_private if hasattr(current_user, 'is_private') else False,
            "is_verified": current_user.is_verified if hasattr(current_user, 'is_verified') else False,
            "created_at": current_user.created_at
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )

@router.get("/users/{user_id}", response_model=UserResponse, summary="Get user account details")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    user_to_view = db.query(models.User).filter(models.User.id == user_id).first()

    if not user_to_view:
        raise HTTPException(status_code=404, detail="User not found")

    return user_to_view

@router.get("/followers/{user_id}", response_model=List[UserResponse], summary="Foydalanuvchining followerlarini olish")
def get_followers(user_id: int, db: Session = Depends(get_db)):
    followers = db.query(models.Follower).filter(models.Follower.followed_id == user_id).all()
    follower_ids = [f.follower_id for f in followers]
    users = db.query(models.User).filter(models.User.id.in_(follower_ids)).all()
    return users

@router.get("/following/{user_id}", response_model=List[UserResponse], summary="Foydalanuvchining followinglarini olish")
def get_following(user_id: int, db: Session = Depends(get_db)):
    following = db.query(models.Follower).filter(models.Follower.follower_id == user_id).all()
    following_ids = [f.followed_id for f in following]
    users = db.query(models.User).filter(models.User.id.in_(following_ids)).all()
    return users

# Post ko'rilganida noyob yozuv qo'shish funksiyasi
# Bu funksiya post ko'rilgan joyda chaqirilishi kerak
def add_post_view(post_id: int, user_id: int, db: Session):
    existing_view = db.query(models.PostView).filter(
        models.PostView.post_id == post_id,
        models.PostView.owner_id == user_id
    ).first()
    if not existing_view:
        new_view = models.PostView(post_id=post_id, owner_id=user_id)
        db.add(new_view)
        try:
            db.commit()
        except Exception:
            db.rollback()

# Eslatma: PostView jadvalida (post_id, owner_id) uchun UNIQUE cheklov bo'lishi kerak
# Bu takroriy yozuvlarning oldini oladi va views soni aniq bo'ladi

@router.get("/posts/{post_id}/views", summary="Post ko'rishlar sonini olish")
def get_post_views(post_id: int, db: Session = Depends(get_db)):
    # Bu funksiya aslida Post modeliga tegishli bo'lishi kerak
    # Hozircha shu yerda qoldirildi
    return {"post_id": post_id, "views": random.randint(100, 1000)}

@router.post("/logout", summary="Logout")
def logout():
    return {"message": "Logout successful"}

@router.put("/change-password/{user_id}", status_code=status.HTTP_200_OK)
async def change_password(
    user_id: int,
    password_data: PasswordUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update user password by verifying the old password first.
    No authentication required.
    """
    # Get the user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "message": "Foydalanuvchi topilmadi"}
        )
    
    # Debug logging for password verification
    print(f"Debug - Verifying password for user: {user_id}")
    print(f"Debug - Provided old password: {password_data.old_password}")
    print(f"Debug - Stored hash: {user.hashed_password}")
    print(f"Debug - Hash type: {type(user.hashed_password)}")
    
    # Verify old password using pwd_context.verify
    is_verified = pwd_context.verify(password_data.old_password, user.hashed_password)
    print(f"Debug - Password verified: {is_verified}")
    
    if not is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Eski parol noto'g'ri"}
        )
    
    # Update password using pwd_context.hash() for consistency
    try:
        user.hashed_password = pwd_context.hash(password_data.new_password)
        
        # Invalidate all existing reset tokens for this user
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.email == user.email
        ).update({"used": True})
        
        db.commit()
        
        return {
            "success": True,
            "message": "Parol muvaffaqiyatli yangilandi"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": f"Parolni yangilashda xatolik yuz berdi: {str(e)}"}
        )

# --- Profile Privacy and App Lock ---

class PrivacyToggleRequest(BaseModel):
    is_private: bool

@router.put(
    "/toggle_privacy",
    response_model=dict,
    summary="Akkaunt maxfiyligini o'zgartirish / Toggle account privacy",
    description="""
    Ushbu endpoint foydalanuvchi hisobining maxfiylik holatini o'zgartiradi.
    - is_private: true - akkauntni yopish (maxfiy qilish)
    - is_private: false - akkauntni ochish (ommaviy qilish)
    """
)
async def toggle_account_privacy(
    request: PrivacyToggleRequest,
    db: Session = Depends(get_db),
):
    # TODO: Add proper authentication
    current_user = db.query(models.User).filter(models.User.id == 1).first()  # Using a dummy user ID
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    current_user.is_private = request.is_private
    db.commit()
    
    return {
        "success": True,
        "message": "Account privacy updated successfully",
        "is_private": current_user.is_private
    }
    return current_user

class SetAppLockRequest(BaseModel):
    """Request model for setting app lock password"""
    user_id: int
    password: str = Field(..., min_length=4, description="New app lock password (min 4 characters)")

@router.post(
    "/set-app-lock",
    status_code=status.HTTP_200_OK,
    summary="Set or change the app lock password",
    response_model=dict,
    responses={
        200: {"description": "App lock password updated successfully"},
        400: {"description": "Invalid request data"},
        404: {"description": "User not found"}
    }
)
async def set_app_lock_password(
    payload: SetAppLockRequest,
    db: Session = Depends(get_db)
):
    """
    Set or change the application lock password.
    
    - **user_id**: ID of the user
    - **password**: New password for app lock (min 4 characters)
    """
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update app lock password
    user.app_lock_password = pwd_context.hash(payload.password)
    db.commit()
    
    return {
        "status": "success", 
        "message": "App lock password updated successfully",
        "user_id": user.id
    }

class VerifyAppLockRequest(BaseModel):
    """Request model for verifying app lock password"""
    user_id: int
    password: str = Field(..., description="App lock password to verify")

@router.post(
    "/verify-app-lock",
    status_code=status.HTTP_200_OK,
    summary="Verify the app lock password",
    response_model=dict,
    responses={
        200: {"description": "App lock password verified successfully"},
        400: {"description": "Invalid request data"},
        401: {"description": "Incorrect app lock password"},
        404: {"description": "User not found or app lock not set up"}
    }
)
async def verify_app_lock_password(
    payload: VerifyAppLockRequest,
    db: Session = Depends(get_db)
):
    """
    Verify the application lock password.
    
    - **user_id**: ID of the user
    - **password**: The app lock password to verify
    """
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.app_lock_password:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App lock is not set up for this user"
        )
    
    if not pwd_context.verify(payload.password, user.app_lock_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect app lock password"
        )
    
    return {
        "status": "success", 
        "message": "App lock password verified",
        "user_id": user.id
    }

# --- Follow and Follow Request Logic ---

@router.post("/follow/{user_to_follow_id}", summary="Follow a user or send a follow request")
def follow_user(user_to_follow_id: int, db: Session = Depends(get_db)):
    requester_id = 1
    if requester_id == user_to_follow_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot follow yourself.")

    user_to_follow = db.query(models.User).filter(models.User.id == user_to_follow_id).first()
    if not user_to_follow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Check if already following or request is pending
    existing_follow = db.query(models.Follower).filter_by(follower_id=requester_id, followed_id=user_to_follow_id).first()
    if existing_follow:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are already following this user.")
    
    pending_request = db.query(models.FollowRequest).filter_by(requester_id=requester_id, requested_id=user_to_follow_id, status='pending').first()
    if pending_request:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Follow request already sent.")

    if user_to_follow.is_private:
        # Create a follow request
        follow_request = models.FollowRequest(requester_id=requester_id, requested_id=user_to_follow_id)
        db.add(follow_request)
        db.commit()
        return {"status": "request_sent"}
    else:
        # Follow directly
        new_follow = models.Follower(follower_id=requester_id, followed_id=user_to_follow_id)
        db.add(new_follow)
        db.commit()
        return {"status": "following"}

@router.get("/follow-requests", response_model=List[PasswordUpdateRequest], summary="Get pending follow requests")
def get_follow_requests(db: Session = Depends(get_db)):
    requests = db.query(models.FollowRequest).filter_by(requested_id=1, status='pending').all()
    return requests

@router.post("/follow-requests/{request_id}/accept", summary="Accept a follow request")
def accept_follow_request(request_id: int, db: Session = Depends(get_db)):
    request = db.query(models.FollowRequest).filter_by(id=request_id, requested_id=1, status='pending').first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found or already handled.")

    request.status = 'accepted'
    new_follow = models.Follower(follower_id=request.requester_id, followed_id=request.requested_id)
    db.add(new_follow)
    db.commit()
    return {"status": "accepted"}

@router.post("/follow-requests/{request_id}/decline", summary="Decline a follow request")
def decline_follow_request(request_id: int, db: Session = Depends(get_db)):
    request = db.query(models.FollowRequest).filter_by(id=request_id, requested_id=1, status='pending').first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found or already handled.")

    request.status = 'declined'
    db.commit()
    return {"status": "declined"}

# --- Get Profile Logic (Handles Private Profiles) ---

@router.get("/{user_id}", response_model=UserResponse, summary="Get user profile")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    viewer_id = 1
    user_to_view = db.query(models.User).filter(models.User.id == user_id).first()

    if not user_to_view:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user_to_view.is_private or user_id == viewer_id:
        return user_to_view

    # Check if viewer is a follower
    is_follower = db.query(models.Follower).filter_by(follower_id=viewer_id, followed_id=user_id).first()
    if is_follower:
        return user_to_view
    else:
        return {"error": "Private profile"}
