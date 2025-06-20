import json

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Request, Query, status
from sqlalchemy.orm import joinedload
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
import shutil
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func

import models
import schemas
from database import SessionLocal
from main import get_current_user

# Ensure upload directories exist
STORY_UPLOAD_DIR = "media/stories"
os.makedirs(STORY_UPLOAD_DIR, exist_ok=True)

# Response Models
class StoryResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_avatar: Optional[str] = None
    text: Optional[str] = None
    image: Optional[str] = None
    video: Optional[str] = None
    created_at: str
    likes_count: int
    comments_count: int
    is_owner: bool
    is_liked: bool

class StoriesResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

# Initialize router with proper metadata
router = APIRouter(
    prefix="",  # Prefix is set in main.py
    responses={404: {"description": "Not found"}},
)

def get_db():
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        print(f"Database error: {e}")
        raise
    finally:
        db.close()

# Storyga like qo'yish
@router.post(
    "/{story_id}/like",
    summary="Storyga like qo'yish",
    operation_id="like_story"
)
def like_story(
    story_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Like/unlike a story.
    
    If the user has already liked the story, it will be unliked.
    If the user hasn't liked the story, it will be liked.
    """
    # Check if story exists
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story topilmadi")

    # Check if the story owner has blocked the current user
    block = db.query(models.Block).filter(
        (models.Block.blocked_user_id == current_user.id) & 
        (models.Block.blocking_user_id == story.owner_id)
    ).first()
    
    if block:
        raise HTTPException(status_code=403, detail="You are blocked by the story owner")

    # Check if the current user has blocked the story owner
    block = db.query(models.Block).filter(
        (models.Block.blocked_user_id == story.owner_id) & 
        (models.Block.blocking_user_id == current_user.id)
    ).first()
    
    if block:
        raise HTTPException(status_code=403, detail="You have blocked the story owner")
    
    # Check if user already liked the story
    already = db.query(models.StoryLike).filter(
        models.StoryLike.owner_id == current_user.id,
        models.StoryLike.story_id == story_id
    ).first()
    
    if already:
        # If already liked, remove the like
        db.delete(already)
        db.commit()
        return {"message": "Like o'chirildi", "liked": False}
    else:
        # If not liked, add new like
        like = models.StoryLike(owner_id=current_user.id, story_id=story_id)
        db.add(like)
        db.commit()
        db.refresh(like)
        
        # Return the created like
        return {
            "id": like.id,
            "user_id": like.owner_id,
            "story_id": like.story_id,
            "created_at": like.created_at
        }

# Storyga comment va stikerli comment qo'yish
@router.post(
    "/{story_id}/comment", 
    summary="Storyga comment yozish",
    operation_id="comment_story",
    status_code=201
)
def comment_story(
    story_id: int, 
    text: str = Form(None, description="Comment matni"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # Check if story exists
        story = db.query(models.Story).filter(models.Story.id == story_id).first()
        if not story:
            raise HTTPException(status_code=404, detail="Story topilmadi")
            
        # Create comment using current user's ID
        comment = models.StoryComment(
            owner_id=current_user.id,
            story_id=story_id,
            text=text
        )
        db.add(comment)
        db.commit()
        db.refresh(comment)
        
        # Get user info for response
        user = current_user
        
        return {
            "success": True,
            "message": "Comment muvaffaqiyatli qo'shildi",
            "data": {
                "id": comment.id,
                "user_id": comment.owner_id,
                "story_id": comment.story_id,
                "text": comment.text,
                "created_at": comment.created_at.isoformat(),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "avatar_url": getattr(user, 'avatar_url', None)
                } if user else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Comment qo'shishda xatolik: {str(e)}")

# Story kommentlarini olish
@router.get(
    "/{story_id}/comments",
    summary="Storydagi kommentlarni olish",
    operation_id="get_story_comments"
)
def get_story_comments(
    story_id: int,
    page: int = Query(1, ge=1, description="Sahifa raqami"),
    per_page: int = Query(20, ge=1, le=100, description="Har sahifadagi kommentlar soni"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # Check if story exists
        story = db.query(models.Story).filter(models.Story.id == story_id).first()
        if not story:
            raise HTTPException(status_code=404, detail="Story topilmadi")
        
        # Get total count for pagination
        total = db.query(models.StoryComment).filter(
            models.StoryComment.story_id == story_id
        ).count()
        
        # Get paginated comments with block checks
        offset = (page - 1) * per_page
        comments = db.query(models.StoryComment).options(
            joinedload(models.StoryComment.user)
        ).filter(
            models.StoryComment.story_id == story_id
        ).order_by(
            models.StoryComment.created_at.desc()
        ).offset(offset).limit(per_page).all()

        # Filter out comments from users that the current user has blocked
        comments = [
            comment for comment in comments 
            if not db.query(models.Block).filter(
                (models.Block.blocked_user_id == comment.user_id) & 
                (models.Block.blocking_user_id == current_user.id)
            ).first()
        ]
        
        # Format response
        comments_data = []
        for comment in comments:
            comment_data = {
                "id": comment.id,
                "text": comment.text,
                "created_at": comment.created_at.isoformat(),
                "user": {
                    "id": comment.user.id,
                    "username": comment.user.username,
                    "avatar_url": getattr(comment.user, 'avatar_url', None)
                },
                "reply_count": len(comment.replies) if hasattr(comment, 'replies') else 0
            }
            comments_data.append(comment_data)
        
        return {
            "success": True,
            "data": comments_data,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kommentlarni olishda xatolik: {str(e)}")

# Storyga kim like bosganini ko'rish
@router.get("/{story_id}/likes", summary="Storyga kim like bosganini ko'rish")
def story_likes(
    story_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if story exists
    story = db.query(models.Story).filter(models.Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story topilmadi")

    # Check if the story owner has blocked the current user
    block = db.query(models.Block).filter(
        (models.Block.blocked_user_id == current_user.id) & 
        (models.Block.blocking_user_id == story.owner_id)
    ).first()
    
    if block:
        raise HTTPException(status_code=403, detail="You are blocked by the story owner")

    # Check if the current user has blocked the story owner
    block = db.query(models.Block).filter(
        (models.Block.blocked_user_id == story.owner_id) & 
        (models.Block.blocking_user_id == current_user.id)
    ).first()
    
    if block:
        raise HTTPException(status_code=403, detail="You have blocked the story owner")

    # Get likes and filter out users that the current user has blocked
    likes = db.query(models.StoryLike).options(
        joinedload(models.StoryLike.user)
    ).filter(models.StoryLike.story_id == story_id).all()

    # Filter out likes from users that the current user has blocked
    filtered_likes = [
        {
            "user_id": like.owner_id,
            "user": {
                "id": like.user.id,
                "username": like.user.username,
                "avatar_url": getattr(like.user, 'avatar_url', None)
            }
        }
        for like in likes 
        if not db.query(models.Block).filter(
            (models.Block.blocked_user_id == like.owner_id) & 
            (models.Block.blocking_user_id == current_user.id)
        ).first()
    ]

    return filtered_likes

# 24 soatdan so'ng avtomatik o'chirish (startup.py yoki background taskda chaqiriladi)
def delete_expired_stories():
    db = next(get_db())
    now = datetime.utcnow()
    expired = db.query(models.Story).filter(models.Story.expires_at < now).all()
    for story in expired:
        # Delete associated files
        if story.image and os.path.exists(story.image):
            os.remove(story.image)
        if story.video and os.path.exists(story.video):
            os.remove(story.video)
        db.delete(story)
    db.commit()

# Create a new story
from fastapi import Request
from fastapi.responses import JSONResponse



def save_upload_file(upload_file, upload_dir, allowed_extensions):
    """Save uploaded file to the specified directory"""
    if not upload_file or not hasattr(upload_file, 'filename') or not upload_file.filename:
        return None
        
    file_ext = os.path.splitext(upload_file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        return None
        
    # Create upload directory if it doesn't exist
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    filename = f"story_{int(datetime.utcnow().timestamp())}{file_ext}"
    file_path = os.path.join(upload_dir, filename)
    
    # Save the file
    with open(file_path, "wb") as buffer:
        content = upload_file.file.read()
        buffer.write(content)
    
    return file_path

from pydantic import BaseModel

# StoryCreate class removed as we don't need it

@router.post(
    "/create",
    summary="Yangi story yaratish",
    operation_id="create_story",
    response_model=StoryResponse
)
async def create_story(
    text: str = Form(""),
    media: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Create a new story with media file.
    """
    try:
        # Ensure upload directory exists
        os.makedirs(STORY_UPLOAD_DIR, exist_ok=True)
        
        # Validate file
        if not media or not media.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")
            
        # Get file info
        file_ext = os.path.splitext(media.filename.lower())[1]
        content_type = media.content_type or ''
        
        # Validate file type
        is_image = content_type.startswith('image/') or file_ext in ['.jpg', '.jpeg', '.png', '.gif']
        is_video = content_type.startswith('video/') or file_ext in ['.mp4', '.mov', '.avi']
        
        if not (is_image or is_video):
            raise HTTPException(status_code=400, detail="Unsupported file type")
            
        # Generate unique filename
        filename = f"story_{int(datetime.utcnow().timestamp())}{file_ext}"
        file_path = os.path.join(STORY_UPLOAD_DIR, filename)
        
        # Save the file
        with open(file_path, "wb") as buffer:
            content = await media.read()
            buffer.write(content)
            
        # Check if user has reached the daily story limit
        today = datetime.now().date()
        daily_limit = 10  # Maximum number of stories per day
        
        stories_today = db.query(models.Story).filter(
            models.Story.owner_id == current_user.id,
            func.date(models.Story.created_at) == today
        ).count()
        
        if stories_today >= daily_limit:
            raise HTTPException(status_code=403, detail="Daily story limit reached")

        # Check if user has reached the total story limit
        total_limit = 100  # Maximum total stories
        
        total_stories = db.query(models.Story).filter(
            models.Story.owner_id == current_user.id
        ).count()
        
        if total_stories >= total_limit:
            raise HTTPException(status_code=403, detail="Total story limit reached")

        # Check if user has any active blocks
        blocked_by = db.query(models.Block).filter(
            models.Block.blocked_user_id == current_user.id
        ).count()
        
        if blocked_by > 0:
            raise HTTPException(status_code=403, detail="Cannot create story while blocked by other users")

        # Create story
        story = models.Story(
            owner_id=current_user.id,
            text=text,
            media_url=file_path,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        
        # Process mentions after story is created
        mentioned_users = []
        if text:
            mention_pattern = r'@(\w+)'
            usernames = re.findall(mention_pattern, text)
            
            # Get mentioned users if there are any mentions
            if usernames:
                users = db.query(models.User).filter(
                    models.User.username.in_(usernames)
                ).all()
                mentioned_users = [user.id for user in users]
                
                # Create notifications for mentioned users
                if mentioned_users:
                    # Get the current user who created the story
                    username = current_user.username
                    
                    for user_id in mentioned_users:
                        notification = models.Notification(
                            user_id=user_id,
                            type='mention',
                            content=f"You were mentioned in a story by {username}",
                            is_read=False
                        )
                        db.add(notification)
                    db.commit()
        
        return {
            "success": True,
            "message": "Story created successfully",
            "story_id": story.id,
            "media_url": file_path
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        # Clean up file if it was created
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Error creating story: {str(e)}")
    finally:
        # Ensure file is closed
        if 'media' in locals() and hasattr(media, 'file'):
            try:
                media.file.close()
            except:
                pass
            
            # Get user info for response
            user = db.query(models.User).filter(models.User.id == user_id).first()
            
            # Prepare response data
            response_data = {
                "id": story.id,
                "user_id": story.owner_id,
                "user_name": user.username if user else "Unknown",
                "user_avatar": user.avatar_url if user and hasattr(user, 'avatar_url') else None,
                "text": text,
                "media": story.media_url,
                "media_type": story.media_type,
                "created_at": story.created_at.isoformat(),
                "expires_at": story.expires_at.isoformat() if story.expires_at else None,
                "likes_count": 0,
                "comments_count": 0,
                "is_owner": True,
                "is_liked": False
            }
            
            return {
                "success": True,
                "message": "Story created successfully",
                "data": response_data
            }

@router.get("/following-stories", response_model=dict)
async def get_following_stories(
    user_id: int = Query(..., description="ID of the user whose following's stories to fetch"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get stories from users that the specified user follows.
    Returns a list of stories with user information and view status.
    """
    try:
        # Check if the user exists
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if the current user has blocked the target user
        block = db.query(models.Block).filter(
            (models.Block.blocked_user_id == user_id) & 
            (models.Block.blocking_user_id == current_user.id)
        ).first()
        
        if block:
            raise HTTPException(status_code=403, detail="You have blocked this user")

        # Check if the target user has blocked the current user
        block = db.query(models.Block).filter(
            (models.Block.blocked_user_id == current_user.id) & 
            (models.Block.blocking_user_id == user_id)
        ).first()
        
        if block:
            raise HTTPException(status_code=403, detail="This user has blocked you")

        # Get the list of user IDs that the specified user follows
        following_users = db.query(models.Follower.followed_id).filter(
            models.Follower.follower_id == user_id
        ).subquery('following_users')
        
        # Get active stories from followed users (not expired)
        current_time = datetime.utcnow()
        stories = db.query(models.Story).filter(
            models.Story.owner_id.in_(following_users),
            models.Story.expires_at > current_time
        ).order_by(models.Story.created_at.desc()).all()

        # Filter out stories from blocked users
        filtered_stories = []
        for story in stories:
            # Check if the story owner has blocked the current user
            block = db.query(models.Block).filter(
                (models.Block.blocked_user_id == current_user.id) & 
                (models.Block.blocking_user_id == story.owner_id)
            ).first()
            
            if not block:
                # Check if the current user has blocked the story owner
                block = db.query(models.Block).filter(
                    (models.Block.blocked_user_id == story.owner_id) & 
                    (models.Block.blocking_user_id == current_user.id)
                ).first()
                
                if not block:
                    filtered_stories.append(story)
        
        # Get stories that the user has already viewed
        viewed_story_ids = db.query(models.StoryView.story_id).filter(
            models.StoryView.owner_id == user_id,
            models.StoryView.story_id.in_([story.id for story in filtered_stories])
        ).all()
        viewed_story_ids = {story_id for (story_id,) in viewed_story_ids}
        
        # Format the response
        result = []
        for story in stories:
            # Get user info
            user = db.query(models.User).filter(models.User.id == story.owner_id).first()
            
            result.append({
                "id": story.id,
                "user_id": story.owner_id,
                "user_name": user.username if user else "Unknown",
                "user_avatar": user.avatar_url if user and hasattr(user, 'avatar_url') else None,
                "media": story.media_url,
                "media_type": story.media_type,
                "created_at": story.created_at.isoformat(),
                "expires_at": story.expires_at.isoformat() if story.expires_at else None,
                "is_viewed": story.id in viewed_story_ids,
                "view_count": story.view_count,
                "like_count": story.like_count,
                "comment_count": story.comment_count
            })
        
        return {
            "success": True,
            "data": result,
            "count": len(result)
        }
        
    except Exception as e:
        return {
            "success": False,
            "detail": f"Error fetching following stories: {str(e)}"
        }

# Get stories
from fastapi import Query
from typing import Optional

@router.get("", 
    response_model=StoriesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stories",
    operation_id="get_all_stories",
    description="""
    Get stories with filtering options.
    - If user_id is provided, returns stories only from that user
    - current_user_id is used to show ownership and like status
    """,
    responses={
        200: {"description": "List of stories"},
        400: {"description": "Invalid input"},
        500: {"description": "Internal server error"}
    }
)
async def get_stories(
    user_id: Optional[int] = Query(
        None, 
        description="Filter stories by user ID"
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        # Base query with proper relationship name and block filters
        query = db.query(models.Story)\
            .options(joinedload(models.Story.user))\
            .order_by(models.Story.created_at.desc())
        
        # Filter by user_id if provided and check block relationships
        if user_id:
            # Check if user exists
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
                
            # Check if current user has blocked the target user
            block = db.query(models.Block).filter(
                (models.Block.blocked_user_id == user_id) & 
                (models.Block.blocking_user_id == current_user.id)
            ).first()
            
            if block:
                raise HTTPException(status_code=403, detail="You have blocked this user")
                
            # Check if target user has blocked current user
            block = db.query(models.Block).filter(
                (models.Block.blocked_user_id == current_user.id) & 
                (models.Block.blocking_user_id == user_id)
            ).first()
            
            if block:
                raise HTTPException(status_code=403, detail="This user has blocked you")
                
            query = query.filter(models.Story.owner_id == int(user_id))
        
        # Execute query
        stories = query.all()
        
        # Filter out stories from blocked users
        filtered_stories = []
        for story in stories:
            # Skip if story is expired
            if story.expires_at and story.expires_at <= datetime.utcnow():
                continue
                
            # Check if story owner has blocked current user
            block = db.query(models.Block).filter(
                (models.Block.blocked_user_id == current_user.id) & 
                (models.Block.blocking_user_id == story.owner_id)
            ).first()
            
            if block:
                continue
                
            # Check if current user has blocked story owner
            block = db.query(models.Block).filter(
                (models.Block.blocked_user_id == story.owner_id) & 
                (models.Block.blocking_user_id == current_user.id)
            ).first()
            
            if block:
                continue
                
            filtered_stories.append(story)
        
        # Format the response
        result = []
        for story in stories:
            # Handle media_url (can be string or JSON)
            media_type = None
            media_url = None
            
            if story.media_url:
                try:
                    # Try to parse as JSON first
                    media_info = json.loads(story.media_url)
                    media_type = media_info.get('type')
                    media_url = media_info.get('url')
                except (json.JSONDecodeError, AttributeError):
                    # If not JSON, use as direct URL and guess type from extension
                    media_url = story.media_url
                    if any(ext in media_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        media_type = 'image'
                    elif any(ext in media_url.lower() for ext in ['.mp4', '.webm', '.mov']):
                        media_type = 'video'
            
            story_data = {
                "id": story.id,
                "user_id": story.owner_id,
                "user_name": story.user.username if story.user else "Unknown",
                "user_avatar": story.user.avatar_url if story.user and hasattr(story.user, 'avatar_url') else None,
                "text": "",  # Text field is not used in the model
                "image": media_url if media_type == 'image' else None,
                "video": media_url if media_type == 'video' else None,
                "created_at": story.created_at.isoformat(),
                "likes_count": len(story.likes),
                "comments_count": len(story.comments),
                "is_owner": False,
                "is_liked": False
            }
            
            # Check if current user is the owner
            if str(story.owner_id) == str(current_user.id):
                story_data["is_owner"] = True
                
            # Check if current user liked this story
            if any(like.owner_id == current_user.id for like in story.likes):
                story_data["is_liked"] = True
                
            result.append(story_data)
        
        return {
            "success": True,
            "data": {
                "stories": result,
                "total": len(result)
            }
        }
        
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "detail": "Invalid user_id format"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Error fetching stories: {str(e)}"}
        )

# Delete a story (owner only)
@router.delete(
    "/{story_id}", 
    status_code=200, 
    summary="Delete a story. Only the story owner can delete their own story.",
    operation_id="delete_story",
    responses={
        200: {"description": "Story deleted successfully"},
        400: {"description": "Missing or invalid user_id"},
        403: {"description": "Not authorized to delete this story"},
        404: {"description": "Story not found"}
    }
)
async def delete_story(
    story_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Delete a story. Only the story owner can delete their own story.
    """
    try:
        # Get the story
        story = db.query(models.Story).filter(
            models.Story.id == story_id
        ).first()
        
        if not story:
            return JSONResponse(
                status_code=404,
                content={"success": False, "detail": "Story not found"}
            )
        
        # Check if current user is the story owner
        if story.owner_id != current_user.id:
            return JSONResponse(
                status_code=403,
                content={"success": False, "detail": "You can only delete your own stories"}
            )
        
        # Delete associated files
        if story.media_url:
            try:
                media_info = json.loads(story.media_url) if isinstance(story.media_url, str) else story.media_url
                if isinstance(media_info, dict):
                    file_path = media_info.get('url')
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
            except (json.JSONDecodeError, AttributeError):
                if os.path.exists(story.media_url):
                    os.remove(story.media_url)
        
        # Delete all comments and likes for this story
        db.query(models.StoryComment).filter(
            models.StoryComment.story_id == story_id
        ).delete(synchronize_session=False)
        
        db.query(models.StoryLike).filter(
            models.StoryLike.story_id == story_id
        ).delete(synchronize_session=False)
        
        # Delete the story
        db.delete(story)
        db.commit()
        
        return {"success": True, "message": "Story deleted successfully"}
        
        # Return 204 No Content
        return None
        
    except Exception as e:
        if 'db' in locals():
            db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error deleting story: {str(e)}"}
        )
