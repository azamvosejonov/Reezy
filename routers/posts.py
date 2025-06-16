import re
import shutil
import json
import sqlalchemy
from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Request, Body, status, Query
from pydantic import BaseModel, Field
from typing import Optional, Union, List
from sqlalchemy.orm import Session

import models
import schemas
import os
from database import SessionLocal
from datetime import datetime
from routers.auth import get_current_user

# Ensure upload directories exist
POST_UPLOAD_DIR = "media/posts"
os.makedirs(POST_UPLOAD_DIR, exist_ok=True)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_uploaded_file(file: UploadFile, upload_dir: str, allowed_extensions: list) -> str:
    """Save uploaded file and return the file path"""
    try:
        if not file or not hasattr(file, 'filename') or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        file_ext = os.path.splitext(file.filename)[1].lower()
        if not file_ext or file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )

        # Ensure upload directory exists with proper permissions
        try:
            os.makedirs(upload_dir, exist_ok=True, mode=0o755)
            # Test if directory is writable
            test_file = os.path.join(upload_dir, '.test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot write to upload directory {upload_dir}: {str(e)}"
            )

        # Generate unique filename
        timestamp = int(datetime.utcnow().timestamp())
        filename = f"post_{timestamp}{file_ext}"
        file_path = os.path.abspath(os.path.join(upload_dir, filename))
        print(f"Attempting to save file to: {file_path}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Directory exists: {os.path.exists(upload_dir)}")
        print(f"Directory permissions: {oct(os.stat(upload_dir).st_mode)[-3:]}")

        # Save the file
        try:
            # Reset file pointer to start in case it was read before
            if hasattr(file.file, 'seek'):
                file.file.seek(0)

            # Save file in chunks to handle large files
            with open(file_path, 'wb') as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Verify file was written
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise HTTPException(status_code=500, detail="Failed to save file")

            return file_path

        except Exception as e:
            # Clean up if file was partially written
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
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
    body: str = Field("", description="Text content of the post")
    duration: Optional[int] = Field(None, description="Duration of video in seconds (required if video is attached)")

@router.post(
    "/create", 
    summary="Create a new post",
    response_model=schemas.Post,
    status_code=status.HTTP_201_CREATED
)
async def create_post(
    user_id: int = Form(...),
    body: Optional[str] = Form(None),
    media: Optional[UploadFile] = File(None, description="Media file (image or video) for the post"),
    duration: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Create a new post with text and optional media (image or video).
    """
    media_info = None
    media_path = None
    
    try:
        if media and hasattr(media, 'filename') and media.filename:
            # Get file info
            file_ext = os.path.splitext(media.filename.lower())[1]
            content_type = media.content_type or ''
            
            # Validate file type
            is_image = content_type.startswith('image/') or file_ext in ['.jpg', '.jpeg', '.png', '.gif']
            is_video = content_type.startswith('video/') or file_ext in ['.mp4', '.mov', '.avi', '.mkv']
            
            if not (is_image or is_video):
                raise HTTPException(
                    status_code=400,
                    detail="Noto'g'ri fayl formati. Ruxsat etilgan formatlar: JPG, JPEG, PNG, GIF, MP4, MOV, AVI, MKV"
                )
            
            # For videos, check if duration is provided
            if is_video and not duration:
                raise HTTPException(
                    status_code=400,
                    detail="Video davomiyligi kiritilishi shart"
                )
            
            # Save the file
            media_path = save_uploaded_file(
                media,
                POST_UPLOAD_DIR,
                ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.avi', '.mkv']
            )
            
            # Prepare media info
            media_type = "image" if is_image else "video"
            media_info = {
                'url': media_path,
                'type': media_type,
                'created_at': datetime.utcnow().isoformat()
            }
            
            if is_video:
                media_info['duration'] = duration or 0
    
    except HTTPException:
        raise
    except Exception as e:
        # Clean up any partially uploaded file
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
            except:
                pass
        raise HTTPException(
            status_code=500,
            detail=f"Faylni yuklashda xatolik: {str(e)}"
        )
    finally:
        # Ensure file is closed
        if media and hasattr(media, 'file'):
            try:
                media.file.close()
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
    post = db.query(models.Post).filter(models.Post.id == post_id, models.Post.owner_id == user_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi yoki ruxsat yo'q")
    db.delete(post)
    db.commit()
    return {"detail": "Post o'chirildi"}

# Barcha postlar (random tartibda)
@router.get("/all_random", response_model=list[schemas.Post], summary="Barcha postlar random tartibda")
def get_all_posts_random(db: Session = Depends(get_db)):
    # Get posts with owner relationship loaded
    posts = db.query(models.Post).options(
        sqlalchemy.orm.joinedload(models.Post.owner)
    ).all()
    
    import random
    random.shuffle(posts)
    
    formatted_posts = []
    for post in posts:
        media_info = {
            'url': post.media_url,
            'type': post.media_type,
            'created_at': post.created_at.isoformat()
        } if post.media_url and post.media_type else {}
        media_type = media_info.get('type')
        
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
            "user": user_info if user_info else {"id": post.user_id, "username": "Unknown", "profile_picture": None} if user_info else {"id": post.user_id, "username": "Unknown", "profile_picture": None}
        }
        formatted_posts.append(formatted_post)
        
    return formatted_posts

# Barcha post videolar (random tartibda)
@router.get("/all_videos_random", response_model=list[schemas.Post], summary="Barcha post videolar random tartibda")
def get_all_post_videos_random(db: Session = Depends(get_db)):
    # Get posts with owner relationship loaded and filter for videos
    posts = db.query(models.Post).options(
        sqlalchemy.orm.joinedload(models.Post.owner)
    ).all()
    
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
            "user": user_info if user_info else {"id": post.user_id, "username": "Unknown", "profile_picture": None} if user_info else {"id": post.user_id, "username": "Unknown", "profile_picture": None}
        }
        video_posts.append(formatted_post)
        
    return video_posts

# Like bosish va notification
@router.post("/like", response_model=schemas.Like, summary="Postga like qo'yish va notification")
def like_post(like: schemas.LikeCreate, db: Session = Depends(get_db)):
    db_like = db.query(models.Like).filter(
        models.Like.owner_id == like.user_id,
        models.Like.post_id == like.post_id
    ).first()
    if db_like:
        raise HTTPException(status_code=400, detail="Already liked")
    new_like = models.Like(owner_id=like.user_id, post_id=like.post_id)
    db.add(new_like)
    # Notification
    post = db.query(models.Post).filter(models.Post.id == like.post_id).first()
    if post and post.owner_id != like.user_id:  # Don't notify if user likes their own post
        notif = models.Notification(
            user_id=post.owner_id,
            message=f"Sizning postingizga like bosildi: user_id={like.user_id}",
            is_read=False
        )
        db.add(notif)
    db.commit()
    db.refresh(new_like)
    
    # Return response matching schemas.Like
    return {
        "id": new_like.id,
        "user_id": new_like.owner_id,  # Map owner_id to user_id in response
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
            "user": user_info if user_info else {"id": post.user_id, "username": "Unknown", "profile_picture": None} if user_info else {"id": post.user_id, "username": "Unknown", "profile_picture": None}
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
    
    # Get the post to send notification to post owner
    post = db.query(models.Post).options(
        sqlalchemy.orm.joinedload(models.Post.owner)
    ).filter(models.Post.id == post_id).first()
    
    # Send notification if not commenting on own post
    if post and post.owner_id != user_id:
        notification = models.Notification(
            user_id=post.owner_id,
            message=f"Sizning postingizga foydalanuvchi {user_id} komment qo'shdi",
            is_read=False
        )
        db.add(notification)
    
    db.commit()
    db.refresh(db_comment)
    
    # Get user info for response
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    return {
        "id": db_comment.id,
        "content": db_comment.text,
        "post_id": db_comment.post_id,
        "user_id": db_comment.owner_id,
        "created_at": db_comment.created_at,
        "updated_at": db_comment.created_at,  # Same as created_at for new comments
        "user": {
            "id": user.id,
            "username": user.username,
            "profile_picture": user.profile_picture
        },
        "like_count": 0,  # New comment has 0 likes
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
def forward_post(post_id: int = Form(...), to_user_ids: str = Form(...), user_id: int = Form(...), db: Session = Depends(get_db)):
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
def get_post_detail(post_id: int, user_id: int = Query(..., description="Current user ID"), db: Session = Depends(get_db)):
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
    media_info = json.loads(post.media_url) if post.media_url else {}
    media_type = media_info.get('type')
    
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
        "updated_at": getattr(post, 'updated_at', post.created_at),  # Fallback to created_at if updated_at doesn't exist
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
