import re
import shutil
import json
import sqlalchemy
from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Request, Body, status, Query
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Union, List
from sqlalchemy.orm import Session

import models
import schemas
import os
from database import SessionLocal
from datetime import datetime
from routers.auth import get_current_user, logger

BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize media directory
MEDIA_DIR = BASE_DIR / "media" / "posts"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Create subdirectories for images and videos
(MEDIA_DIR / "images").mkdir(exist_ok=True)
(MEDIA_DIR / "videos").mkdir(exist_ok=True)

# IP geolocation data for all countries
COUNTRY_IP_RANGES = {
    # Asia
    '192.168.1.0/24': 'UZ',  # Uzbekistan
    '192.168.2.0/24': 'RU',  # Russia
    '192.168.3.0/24': 'KZ',  # Kazakhstan
    '192.168.4.0/24': 'TM',  # Turkmenistan
    '192.168.5.0/24': 'KG',  # Kyrgyzstan
    '192.168.6.0/24': 'TJ',  # Tajikistan
    '192.168.7.0/24': 'AF',  # Afghanistan
    '192.168.8.0/24': 'IR',  # Iran
    '192.168.9.0/24': 'PK',  # Pakistan
    '192.168.10.0/24': 'CN',  # China
    '192.168.11.0/24': 'MN',  # Mongolia
    '192.168.12.0/24': 'IN',  # India
    '192.168.13.0/24': 'NP',  # Nepal
    '192.168.14.0/24': 'BD',  # Bangladesh
    '192.168.15.0/24': 'MM',  # Myanmar
    '192.168.16.0/24': 'JP',  # Japan
    '192.168.17.0/24': 'KR',  # South Korea
    '192.168.18.0/24': 'VN',  # Vietnam
    '192.168.19.0/24': 'TH',  # Thailand
    '192.168.20.0/24': 'PH',  # Philippines
    '192.168.21.0/24': 'ID',  # Indonesia
    '192.168.22.0/24': 'MY',  # Malaysia
    '192.168.23.0/24': 'SG',  # Singapore
    
    # Europe
    '192.168.24.0/24': 'DE',  # Germany
    '192.168.25.0/24': 'FR',  # France
    '192.168.26.0/24': 'GB',  # United Kingdom
    '192.168.27.0/24': 'IT',  # Italy
    '192.168.28.0/24': 'ES',  # Spain
    '192.168.29.0/24': 'PT',  # Portugal
    '192.168.30.0/24': 'NL',  # Netherlands
    '192.168.31.0/24': 'BE',  # Belgium
    '192.168.32.0/24': 'LU',  # Luxembourg
    '192.168.33.0/24': 'CH',  # Switzerland
    '192.168.34.0/24': 'AT',  # Austria
    '192.168.35.0/24': 'PL',  # Poland
    '192.168.36.0/24': 'CZ',  # Czech Republic
    '192.168.37.0/24': 'HU',  # Hungary
    '192.168.38.0/24': 'RO',  # Romania
    '192.168.39.0/24': 'BG',  # Bulgaria
    '192.168.40.0/24': 'TR',  # Turkey
    
    # North America
    '192.168.41.0/24': 'US',  # United States
    '192.168.42.0/24': 'CA',  # Canada
    '192.168.43.0/24': 'MX',  # Mexico
    
    # South America
    '192.168.44.0/24': 'BR',  # Brazil
    '192.168.45.0/24': 'AR',  # Argentina
    '192.168.46.0/24': 'CL',  # Chile
    '192.168.47.0/24': 'PE',  # Peru
    '192.168.48.0/24': 'CO',  # Colombia
    
    # Africa
    '192.168.49.0/24': 'EG',  # Egypt
    '192.168.50.0/24': 'ZA',  # South Africa
    '192.168.51.0/24': 'NG',  # Nigeria
    '192.168.52.0/24': 'KE',  # Kenya
    '192.168.53.0/24': 'GH',  # Ghana
    '192.168.54.0/24': 'SD',  # Sudan
    '192.168.55.0/24': 'TZ',  # Tanzania
    '192.168.56.0/24': 'UG',  # Uganda
    
    # Middle East
    '192.168.57.0/24': 'SA',  # Saudi Arabia
    '192.168.58.0/24': 'AE',  # United Arab Emirates
    '192.168.59.0/24': 'QA',  # Qatar
    '192.168.60.0/24': 'KW',  # Kuwait
    '192.168.61.0/24': 'BH',  # Bahrain
    '192.168.62.0/24': 'OM',  # Oman
    '192.168.63.0/24': 'YE',  # Yemen
    
    # Oceania
    '192.168.64.0/24': 'AU',  # Australia
    '192.168.65.0/24': 'NZ',  # New Zealand
}

def get_country_from_ip(ip_address: str) -> Optional[str]:
    """Get country code from IP address using our IP range mapping."""
    try:
        # For local development, return Uzbekistan
        if ip_address == '127.0.0.1':
            return 'UZ'
            
        # Get the third octet (subnet) of the IP address
        subnet = '.'.join(ip_address.split('.')[:3]) + '.0/24'
        
        # Look up the country code in our mapping
        return COUNTRY_IP_RANGES.get(subnet)
        
    except Exception as e:
        logger.warning(f"Error getting country from IP {ip_address}: {str(e)}")
        return None

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv']
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS + ALLOWED_VIDEO_EXTENSIONS

# Create subdirectories for images and videos


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_uploaded_file(file: UploadFile, upload_dir: Path, allowed_extensions: list) -> str:
    """Save uploaded file and return the file path"""
    try:
        if not file or not hasattr(file, 'filename') or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        file_ext = Path(file.filename).suffix.lower()
        if not file_ext or file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )

        # Ensure upload directory exists with proper permissions
        try:
            upload_dir.mkdir(parents=True, exist_ok=True)
            upload_dir.chmod(0o755)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot create upload directory {upload_dir}: {str(e)}"
            )

        # Generate unique filename
        timestamp = int(datetime.utcnow().timestamp())
        filename = f"post_{timestamp}{file_ext}"
        file_path = upload_dir / filename

        # Save the file
        try:
            # Reset file pointer to start
            if hasattr(file.file, 'seek'):
                file.file.seek(0)

            # Save file in chunks
            with open(file_path, 'wb') as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Verify file was written
            if not file_path.exists():
                raise HTTPException(status_code=500, detail="Failed to save file")

            # Set proper file permissions
            file_path.chmod(0o644)

            # Return relative path for database storage
            return str(file_path.relative_to(BASE_DIR))

        except Exception as e:
            if file_path.exists():
                try:
                    file_path.unlink()
                except:
                    pass
            raise HTTPException(
                status_code=500,
                detail=f"Error saving file: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error processing file: {str(e)}"
        )


class PostCreate(BaseModel):
    user_id: int = Field(..., description="ID of the user creating the post")
    body: Optional[str] = Field(None, description="Text content of the post")
    duration: Optional[int] = Field(None, description="Duration of video in seconds (required if video is attached)")


@router.post(
    "/create",
    summary="Create a new post",
    response_model=schemas.Post,
    status_code=status.HTTP_201_CREATED
)
async def create_post(
        request: Request,
        user_id: int = Form(..., description="Required user ID"),
        body: Optional[str] = Form(None, description="Optional post body"),
        media_file: UploadFile = File(..., description="Required media file (image or video)"),
        duration: Optional[int] = Form(5),  # Default duration is 5 seconds
        db: Session = Depends(get_db)
):
    """
    Create a new post with text and optional media (image or video).
    """
    media_info = None
    media_path = None

    try:
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required"
            )

        # Handle media upload
        if media_file:  # Direct file upload
            try:
                print(f"File upload attempt: {media_file.filename}")
                print(f"Content type: {media_file.content_type}")
                print(f"File size: {media_file.size}")
                
                # Get file info
                file_ext = Path(media_file.filename).suffix.lower()

                # Validate file type using file extension
                if file_ext not in ALLOWED_EXTENSIONS:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid file type. Allowed: {' '.join(ALLOWED_EXTENSIONS)}"
                    )

                # Determine file type based on extension
                is_image = file_ext in ALLOWED_IMAGE_EXTENSIONS
                is_video = file_ext in ALLOWED_VIDEO_EXTENSIONS

                # Save the file
                timestamp = int(datetime.utcnow().timestamp())
                filename = f"media_{timestamp}{file_ext}"
                
                # Determine directory based on file type
                if is_video:
                    media_dir = MEDIA_DIR / "videos"
                else:
                    media_dir = MEDIA_DIR / "images"
                
                # Create directory if it doesn't exist
                media_dir.mkdir(parents=True, exist_ok=True)
                
                file_path = media_dir / filename
                print(f"Saving file to: {file_path}")

                try:
                    # Reset file pointer to start
                    await media_file.seek(0)
                    
                    # Read file content
                    file_content = await media_file.read()
                    print(f"File read successfully, size: {len(file_content)} bytes")

                    # Write file
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    print("File written successfully")
                    
                    file_path.chmod(0o644)
                    print("File permissions set successfully")

                    # Create media info
                    media_info = {
                        'url': str(file_path.relative_to(BASE_DIR)),
                        'type': 'video' if is_video else 'image',
                        'duration': duration,  # Always use the provided duration
                        'filename': filename
                    }
                    print(f"Media info created: {media_info}")

                except Exception as e:
                    print(f"Error saving file: {str(e)}")
                    if file_path.exists():
                        file_path.unlink()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error saving file: {str(e)}"
                    )

            except Exception as e:
                print(f"File upload error: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"File upload error: {str(e)}"
                )
                
                # Create media info with relative path
                media_info = {
                    'url': str(target_path.relative_to(BASE_DIR)),
                    'type': 'video' if is_video else 'image',
                    'duration': duration if is_video else None
                }

            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Fayl yuklashda xatolik: {str(e)}"
                )

        # Create post
        # Use body if provided, otherwise use an empty string
        post_content = body if body is not None else ''
        
        post = models.Post(
            content=post_content,
            media_url=media_info['url'] if media_info else None,
            media_type=media_info['type'] if media_info else None,
            user_id=user_id,
            created_ip=request.client.host
        )

        # Get country code from IP
        post.country_code = get_country_from_ip(request.client.host)

        # If it's a video, set duration
        if media_info and media_info['type'] == 'video':
            post.duration = media_info['duration']

        # Add to database
        db.add(post)
        db.commit()
        db.refresh(post)

        # Get user info
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # Add user info to post
        post.user = {
            "id": user.id,
            "username": user.username,
            "profile_picture": user.profile_picture
        }

        return post
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Faylni yuklashda xatolik: {str(e)}"
        )
    finally:
        # Ensure file is closed
        if media_file and hasattr(media_file, 'file'):
            try:
                media_file.file.close()
            except:
                pass

    if not body and not media_info:
        raise HTTPException(
            status_code=400,
            detail="Post bo'sh bo'lishi mumkin emas. Matn yoki media fayl kiriting."
        )

    # Convert empty string to None for body
    body = body if body else None

    try:
        # Convert media_info to JSON string if it exists
        media_url = None
        if media_info:
            try:
                media_url = json.dumps(media_info, ensure_ascii=False)
            except Exception as e:
                print(f"Error converting media_info to JSON: {e}")
                media_url = None

        # Create the post with all required fields
        new_post = models.Post(
            content=body or "",  # Ensure content is not None
            media_url=media_url,
            owner_id=user_id
            # created_at is automatically set by the model
        )

        db.add(new_post)
        db.commit()
        db.refresh(new_post)

        # Parse media_url to get image or video URL
        media_type = None
        media_url = None

        if new_post.media_url:
            try:
                media_info = json.loads(new_post.media_url)
                media_type = media_info.get('type')
                media_url = media_info.get('url')
            except Exception as e:
                print(f"Error parsing media_url: {e}")

        # Get user information for the response
        user = db.query(models.User).filter(models.User.id == user_id).first()

        # Create response matching the Post schema
        return {
            "id": new_post.id,
            "body": new_post.content or "",  # Map content to body
            "image": media_url if media_type == 'image' else None,
            "video": media_url if media_type == 'video' else None,
            "user_id": new_post.owner_id,
            "is_ad": False,
            "created_at": new_post.created_at,
            "updated_at": new_post.created_at,  # Same as created_at for new post
            "user": {
                "id": user.id,
                "username": user.username,
                "profile_picture": user.profile_picture
            } if user else None
        }
    except Exception as e:
        db.rollback()
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
            except:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"Could not create post: {str(e)}"
        )


# Post o'chirish (faqat post egasi)
@router.delete("/delete/{post_id}", summary="Postni o'chirish")
def delete_post(post_id: int, user_id: int, db: Session = Depends(get_db)):
    post = db.query(models.Post).filter(models.Post.id == post_id, models.Post.user_id == user_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi yoki ruxsat yo'q")
    db.delete(post)
    db.commit()
    return {"detail": "Post o'chirildi"}


# Barcha postlar (random tartibda)
@router.get("/all_random", response_model=list[schemas.Post], summary="Barcha postlar random tartibda")
def get_all_posts_random(request: Request, db: Session = Depends(get_db)):
    # Get real IP address from request
    client_ip = request.client.host
    
    # Get country from IP address using real IP geolocation service
    country_code = 'UZ'  # Default to Uzbekistan
    try:
        # Use a real IP geolocation service to get country code
        # This is a placeholder - you would need to implement a real service
        if client_ip != '127.0.0.1':
            # Example countries (you would get these from a real geolocation service)
            country_code = {
                '192.168.1.0/24': 'UZ',  # Uzbekistan
                '192.168.2.0/24': 'RU',  # Russia
                '192.168.3.0/24': 'KZ',  # Kazakhstan
                '192.168.4.0/24': 'TM',  # Turkmenistan
                '192.168.5.0/24': 'KG',  # Kyrgyzstan
                '192.168.6.0/24': 'TJ',  # Tajikistan
                '192.168.7.0/24': 'AF',  # Afghanistan
                '192.168.8.0/24': 'IR',  # Iran
                '192.168.9.0/24': 'PK',  # Pakistan
                '192.168.10.0/24': 'CN',  # China
                '192.168.11.0/24': 'MN',  # Mongolia
                '192.168.12.0/24': 'IN',  # India
                '192.168.13.0/24': 'NP',  # Nepal
                '192.168.14.0/24': 'BD',  # Bangladesh
                '192.168.15.0/24': 'MM',  # Myanmar
                # Add more countries as needed
            }.get(client_ip.split('.')[2], 'UZ')  # Default to Uzbekistan
    except Exception as e:
        logger.warning(f"Could not get country from IP: {str(e)}")
        country_code = 'UZ'  # Default to Uzbekistan
    
    # Get country from IP address using our IP geolocation function
    user_country_code = get_country_from_ip(client_ip)
    if not user_country_code:
        user_country_code = 'UZ'  # Default to Uzbekistan
    
    # Get current user's ID from request (assuming it's in the request)
    current_user_id = request.state.user_id if hasattr(request.state, 'user_id') else None
    
    # Get posts with owner information
    posts = db.query(models.Post).options(
        sqlalchemy.orm.joinedload(models.Post.owner)
    ).filter(
        models.Post.country_code == user_country_code
    ).all()
    
    # If user is logged in, add posts from followed users
    if current_user_id:
        # Get followed users
        followed_users = db.query(models.Follow).filter(
            models.Follow.follower_id == current_user_id
        ).all()
        
        # Get posts from followed users
        followed_posts = db.query(models.Post).options(
            sqlalchemy.orm.joinedload(models.Post.owner)
        ).filter(
            models.Post.user_id.in_([f.following_id for f in followed_users])
        ).all()
        
        # Add followed posts to the list
        posts.extend(followed_posts)
        
    # If less than 100 posts found, mix with posts from other countries
    if len(posts) < 100:
        # Get remaining posts from other countries
        other_posts = db.query(models.Post).options(
            sqlalchemy.orm.joinedload(models.Post.owner)
        ).filter(
            models.Post.country_code != user_country_code
        ).all()
        
        # Mix the posts (70% from user's country, 30% from other countries)
        posts.extend(other_posts[:max(0, 100 - len(posts))])
        
    # Shuffle to mix the posts
    import random
    random.shuffle(posts)

    # Format posts
    formatted_posts = []
    for post in posts:
        post_dict = {
            "id": post.id,
            "content": post.content,
            "media_url": post.media_url,
            "media_type": post.media_type,
            "created_at": post.created_at,
            "updated_at": post.updated_at if hasattr(post, 'updated_at') else post.created_at,
            "user_id": post.user_id,
            "country_code": post.country_code,
            "like_count": 0,  # Default to 0 since we don't have like count yet
            "user": {
                "id": post.owner.id,
                "username": post.owner.username,
                "profile_picture": post.owner.profile_picture
            } if post.owner else None
        }
        formatted_posts.append(post_dict)
    
    # Return formatted posts
    return formatted_posts


# Barcha post videolar (random tartibda)
@router.get("/all_videos_random", response_model=list[schemas.Post], summary="Barcha post videolar random tartibda")
def get_all_post_videos_random(request: Request, db: Session = Depends(get_db)):
    # Get real IP address from request
    client_ip = request.client.host
    
    # Get country from IP address using our IP geolocation function
    user_country_code = get_country_from_ip(client_ip)
    if not user_country_code:
        user_country_code = 'UZ'  # Default to Uzbekistan
    
    # Get current user's ID from request (assuming it's in the request)
    current_user_id = request.state.user_id if hasattr(request.state, 'user_id') else None
    
    # Get video posts with owner information
    posts = db.query(models.Post).options(
        sqlalchemy.orm.joinedload(models.Post.owner)
    ).filter(
        models.Post.country_code == user_country_code,
        models.Post.media_type == 'video'
    ).all()
    
    # If user is logged in, add video posts from followed users
    if current_user_id:
        # Get followed users
        followed_users = db.query(models.Follow).filter(
            models.Follow.follower_id == current_user_id
        ).all()
        
        # Get video posts from followed users
        followed_posts = db.query(models.Post).options(
            sqlalchemy.orm.joinedload(models.Post.owner)
        ).filter(
            models.Post.user_id.in_([f.following_id for f in followed_users]),
            models.Post.media_type == 'video'
        ).all()
        
        # Add followed posts to the list
        posts.extend(followed_posts)
        
    # If less than 100 posts found, mix with video posts from other countries
    if len(posts) < 100:
        # Get remaining video posts from other countries
        other_posts = db.query(models.Post).options(
            sqlalchemy.orm.joinedload(models.Post.owner)
        ).filter(
            models.Post.country_code != user_country_code,
            models.Post.media_type == 'video'
        ).all()
        
        # Mix the posts (70% from user's country, 30% from other countries)
        posts.extend(other_posts[:max(0, 100 - len(posts))])
        
    # Shuffle to mix the posts
    import random
    random.shuffle(posts)

    # Format posts
    formatted_posts = []
    for post in posts:
        post_dict = {
            "id": post.id,
            "content": post.content,
            "media_url": post.media_url,
            "media_type": post.media_type,
            "created_at": post.created_at,
            "updated_at": post.updated_at if hasattr(post, 'updated_at') else post.created_at,
            "user_id": post.user_id,
            "country_code": post.country_code,
            "like_count": 0,  # Default to 0 since we don't have like count yet
            "user": {
                "id": post.owner.id,
                "username": post.owner.username,
                "profile_picture": post.owner.profile_picture
            } if post.owner else None
        }
        formatted_posts.append(post_dict)
    
    # Return formatted posts
    return formatted_posts
    
    # Get posts with owner relationship loaded, filter for videos and by country
    posts = db.query(models.Post).options(
        sqlalchemy.orm.joinedload(models.Post.owner)
    ).filter(
        models.Post.media_url.isnot(None),
        models.Post.country_code == user_country_code
    ).all()
    
    # If user is logged in, add posts from followed users
    if current_user_id:
        # Get followed users
        followed_users = db.query(models.Follow).filter(
            models.Follow.follower_id == current_user_id
        ).all()
        
        # Get posts from followed users
        followed_posts = db.query(models.Post).options(
            sqlalchemy.orm.joinedload(models.Post.owner)
        ).filter(
            models.Post.media_url.isnot(None),
            models.Post.user_id.in_([f.following_id for f in followed_users])
        ).all()
        
        # Add followed posts to the list
        posts.extend(followed_posts)
        
    # If less than 100 posts found, mix with posts from other countries
    if len(posts) < 100:
        # Get remaining posts from other countries
        other_posts = db.query(models.Post).options(
            sqlalchemy.orm.joinedload(models.Post.owner)
        ).filter(
            models.Post.media_url.isnot(None),
            models.Post.country_code != user_country_code
        ).all()
        
        # Mix the posts (70% from user's country, 30% from other countries)
        posts.extend(other_posts[:max(0, 100 - len(posts))])
        
        # Shuffle to mix the posts
        import random
        random.shuffle(posts)

    video_posts = []
    import random

    # Filter for video posts
    video_posts_list = []
    for post in posts:
        if post.media_url:
            try:
                media_info = json.loads(post.media_url)
                if media_info.get('type') == 'video':
                    video_posts_list.append((post, media_info))
            except json.JSONDecodeError:
                continue

    # Shuffle the video posts
    random.shuffle(video_posts_list)

    # Format the response
    for post, media_info in video_posts_list:
        # Get owner info
        user_info = None
        if post.owner:
            user_info = {
                "id": post.owner.id,
                "username": post.owner.username,
                "profile_picture": post.owner.profile_picture
            }

        formatted_post = {
            "id": post.id,
            "body": post.content or "",
            "image": None,
            "video": media_info.get('url'),
            "user_id": post.user_id,
            "is_ad": False,
            "created_at": post.created_at,
            "updated_at": post.updated_at if hasattr(post, 'updated_at') else post.created_at,
            "user": user_info if user_info else {"id": post.user_id, "username": "Unknown",
                                                 "profile_picture": None} if user_info else {"id": post.user_id,
                                                                                             "username": "Unknown",
                                                                                             "profile_picture": None}
        }
        video_posts.append(formatted_post)

    return video_posts


# Like bosish va notification
@router.post("/like", response_model=schemas.Like, summary="Postga like qo'yish va notification")
def like_post(like: schemas.LikeCreate, db: Session = Depends(get_db)):
    # Get the owner_id from the schema
    owner_id = like.owner_id or like.user_id
    
    # Check if already liked
    db_like = db.query(models.Like).filter(
        models.Like.owner_id == owner_id,
        models.Like.post_id == like.post_id
    ).first()
    if db_like:
        raise HTTPException(status_code=400, detail="Already liked")
    
    # Create new like
    new_like = models.Like(owner_id=owner_id, post_id=like.post_id)
    db.add(new_like)
    # Notification
    post = db.query(models.Post).filter(models.Post.id == like.post_id).first()
    if post and post.user_id != like.user_id:  # Don't notify if user likes their own post
        notif = models.Notification(
            user_id=post.user_id,
            type='like',
            content=f"Sizning postingizga like bosildi: user_id={like.user_id}",
            is_read=False
        )
        db.add(notif)
    db.commit()
    db.refresh(new_like)

    # Return response matching schemas.Like
    return {
        "id": new_like.id,
        "owner_id": new_like.owner_id,
        "post_id": new_like.post_id,
        "created_at": new_like.created_at if hasattr(new_like, 'created_at') else datetime.utcnow()
    }


# Like bosgan postlarni ko'rish
@router.get("/my_liked_posts", response_model=list[schemas.Post], summary="O'zi like bosgan postlar")
def my_liked_posts(user_id: int, db: Session = Depends(get_db)):
    # Get likes with post and owner relationships loaded
    likes = db.query(models.Like).options(
        sqlalchemy.orm.joinedload(models.Like.post).joinedload(models.Post.owner)
    ).filter(models.Like.owner_id == user_id).all()

    formatted_posts = []
    for like in likes:
        post = like.post
        if not post:
            continue

        # Get like count
        like_count = db.query(models.Like).filter(models.Like.post_id == post.id).count()

        # Get media info
        media_info = {}
        media_type = None
        if post.media_url:
            try:
                media_info = json.loads(post.media_url)
                media_type = media_info.get('type')
            except json.JSONDecodeError:
                pass

        # Get owner info
        user_info = None
        if post.owner:
            user_info = {
                "id": post.owner.id,
                "username": post.owner.username,
                "profile_picture": post.owner.profile_picture
            }

        formatted_post = {
            "id": post.id,
            "body": post.content or "",
            "image": media_info.get('url') if media_type == 'image' else None,
            "video": media_info.get('url') if media_type == 'video' else None,
            "user_id": post.user_id,
            "is_ad": False,
            "created_at": post.created_at,
            "updated_at": post.updated_at if hasattr(post, 'updated_at') else post.created_at,
            "like_count": like_count,
            "user": user_info if user_info else {"id": post.user_id, "username": "Unknown",
                                                 "profile_picture": None} if user_info else {"id": post.user_id,
                                                                                             "username": "Unknown",
                                                                                             "profile_picture": None}
        }
        formatted_posts.append(formatted_post)

    return formatted_posts


# Comment va notification
@router.post("/{post_id}/comment", response_model=schemas.Comment, summary="Komment qo'shish va notification")
async def add_comment(
        post_id: int,
        comment: schemas.CommentBase,
        user_id: int = Body(..., embed=True, description="ID of the user adding the comment"),
        db: Session = Depends(get_db)
):
    # Create the comment
    db_comment = models.Comment(
        text=comment.content,  # Using content field from CommentBase
        owner_id=user_id,
        post_id=post_id
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    # Get the post to send notification to post owner
    post = db.query(models.Post).options(
        sqlalchemy.orm.joinedload(models.Post.owner)
    ).filter(models.Post.id == post_id).first()

    # Send notification if not commenting on own post
    if post and post.user_id != user_id:
        notification = models.Notification(
            user_id=post.user_id,
            message=f"Sizning postingizga foydalanuvchi {user_id} komment qo'shdi",
            is_read=False
        )
        db.add(notification)

    db.commit()
    db.refresh(db_comment)

    # Get user info for response
    user = db.query(models.User).filter(models.User.id == user_id).first()

    # Get comment with relationships
    comment_with_user = db.query(models.Comment).options(
        sqlalchemy.orm.joinedload(models.Comment.owner)
    ).filter(models.Comment.id == db_comment.id).first()
    
    return {
        "id": comment_with_user.id,
        "content": comment_with_user.text,
        "post_id": comment_with_user.post_id,
        "user_id": comment_with_user.owner_id,
        "created_at": comment_with_user.created_at,
        "updated_at": comment_with_user.created_at,
        "user": {
            "id": comment_with_user.owner.id,
            "username": comment_with_user.owner.username,
            "profile_picture": comment_with_user.owner.profile_picture
        },
        "like_count": 0,
        "is_liked": False
    }


# Post commentlarini ko'rish
@router.get("/{post_id}/comments", summary="Post commentlarini ko'rish")
def get_post_comments(post_id: int, db: Session = Depends(get_db)):
    comments = db.query(models.Comment).filter(models.Comment.post_id == post_id).all()
    return comments


# Saqlash (save)
@router.post("/save", summary="Postni saqlash")
async def save_post(
        post_id: int = Form(..., description="ID of the post to save"),
        user_id: int = Form(..., description="ID of the user saving the post"),
        db: Session = Depends(get_db)
):
    # Check if post exists
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")

    # Check if already saved
    existing_save = db.query(models.PostSave).filter(
        models.PostSave.owner_id == user_id,
        models.PostSave.post_id == post_id
    ).first()

    if existing_save:
        raise HTTPException(status_code=400, detail="Bu post allaqachon saqlangan")

    # Create new save
    new_save = models.PostSave(
        owner_id=user_id,
        post_id=post_id,
        saved_at=datetime.utcnow()
    )

    db.add(new_save)
    db.commit()
    db.refresh(new_save)

    # Format response to match schema
    return {
        "id": new_save.id,
        "user_id": new_save.owner_id,  # Map owner_id to user_id in response
        "post_id": new_save.post_id,
        "created_at": new_save.saved_at  # Map saved_at to created_at in response
    }


# Saqlangan postlarni ko'rish
@router.get("/my_saved_posts", summary="O'zi saqlangan postlar")
async def my_saved_posts(
        user_id: int = Query(..., description="ID of the user to get saved posts for"),
        db: Session = Depends(get_db)
):
    # Get all saves for the user with post and owner information
    saves = (
        db.query(models.PostSave)
        .options(
            sqlalchemy.orm.joinedload(models.PostSave.post)
            .joinedload(models.Post.owner)
        )
        .filter(models.PostSave.owner_id == user_id)
        .all()
    )

    # Extract and format posts
    result = []
    for save in saves:
        post = save.post
        if post:
            # Count likes and comments
            like_count = len(post.likes) if hasattr(post, 'likes') else 0
            comment_count = len(post.comments) if hasattr(post, 'comments') else 0

            # Check if current user liked the post
            is_liked = any(like.owner_id == user_id for like in post.likes) if hasattr(post, 'likes') else False

            # Build post data with required fields
            post_data = {
                "id": post.id,
                "user_id": post.user_id,  # Add owner_id to match schema
                "content": post.content,
                "media_url": post.media_url,
                "created_at": post.created_at,
                "updated_at": post.created_at,  # Use created_at as updated_at if not available
                "like_count": like_count,
                "comment_count": comment_count,
                "is_liked": is_liked,
                "user": {
                    "id": post.owner.id,
                    "username": post.owner.username,
                    "profile_picture": getattr(post.owner, 'profile_picture', None)
                }
            }

            # Add media_type if it exists
            if hasattr(post, 'media_type'):
                post_data["media_type"] = post.media_type

            result.append(post_data)

    return result


# Forward (yuborish) - bir yoki bir nechta userga
@router.post("/forward", summary="Postni bir yoki bir nechta userga yuborish")
def forward_post(post_id: int = Form(...), to_user_ids: str = Form(...), user_id: int = Form(...),
                 db: Session = Depends(get_db)):
    # Get the post to forward
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")

    # Parse user IDs
    ids = [int(i) for i in to_user_ids.split(",") if i.strip().isdigit()]

    # Create a message for each recipient
    for to_id in ids:
        # Create a message with post content
        msg = models.Message(
            from_user_id=user_id,
            to_user_id=to_id,
            content=f"Post forward qilindi (Post ID: {post_id})\n\n{post.content}",
            created_at=datetime.utcnow(),
            is_read=False
        )
        db.add(msg)

    db.commit()
    return {"detail": f"Post {len(ids)} foydalanuvchiga yuborildi"}


# Qidiruv (search) - post content bo'yicha
@router.get("/search", summary="Postlarni qidirish (content bo'yicha)")
def search_posts(q: str, db: Session = Depends(get_db)):
    return db.query(models.Post).filter(models.Post.content.ilike(f"%{q}%")).all()


# Post detail endpoint with view count increment
@router.get("/{post_id}", response_model=schemas.Post, summary="Post detail olish")
def get_post_detail(post_id: int, user_id: int = Query(..., description="Current user ID"),
                    db: Session = Depends(get_db)):
    # Get post with owner relationship loaded
    post = db.query(models.Post).options(
        sqlalchemy.orm.joinedload(models.Post.owner)
    ).filter(models.Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")

    # Check if user has viewed this post
    existing_view = db.query(models.PostView).filter(
        models.PostView.post_id == post_id,
        models.PostView.owner_id == user_id
    ).first()

    if not existing_view:
        # Add new view
        new_view = models.PostView(post_id=post_id, owner_id=user_id)
        db.add(new_view)
        db.commit()

    # Get total views count
    views_count = db.query(models.PostView).filter(models.PostView.post_id == post_id).count()

    # Format media info
    media_info = {}
    media_type = None
    if post.media_url:
        try:
            media_info = json.loads(post.media_url)
            media_type = media_info.get('type')
        except json.JSONDecodeError:
            # Handle invalid JSON by treating it as a direct URL
            media_info = {"url": post.media_url}
            media_type = 'image' if post.media_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')) else 'video'

    # Get like and comment counts
    like_count = db.query(models.Like).filter(models.Like.post_id == post_id).count()
    comment_count = db.query(models.Comment).filter(models.Comment.post_id == post_id).count()

    # Check if current user has liked the post
    is_liked = False
    if user_id:
        is_liked = db.query(models.Like).filter(
            models.Like.post_id == post_id,
            models.Like.owner_id == user_id
        ).first() is not None

    # Format response according to Post schema
    formatted_post = {
        "id": post.id,
        "body": post.content or "",
        "image": media_info.get('url') if media_type == 'image' else None,
        "video": media_info.get('url') if media_type == 'video' else None,
        "user_id": post.user_id,
        "is_ad": False,
        "created_at": post.created_at,
        "updated_at": getattr(post, 'updated_at', post.created_at),
        # Fallback to created_at if updated_at doesn't exist
        "views": views_count,
        "like_count": like_count,
        "comment_count": comment_count,
        "is_liked": is_liked,
        "user": {
            "id": post.owner.id,
            "username": post.owner.username,
            "profile_picture": getattr(post.owner, 'profile_picture', None)
        } if post.owner else None
    }

    return formatted_post
