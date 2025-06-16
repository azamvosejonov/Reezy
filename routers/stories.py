import json

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Request, Query, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
import shutil
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_

import models
from database import SessionLocal

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
    tags=["stories"],
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
def like_story(story_id: int, user_id: int = Form(...), db: Session = Depends(get_db)):
    # Check if user already liked the story
    already = db.query(models.StoryLike).filter(
        models.StoryLike.owner_id == user_id, 
        models.StoryLike.story_id == story_id
    ).first()
    
    if already:
        raise HTTPException(status_code=400, detail="Allaqachon like bosilgan")
    
    # Create new like with owner_id
    like = models.StoryLike(owner_id=user_id, story_id=story_id)
    db.add(like)
    db.commit()
    db.refresh(like)
    
    # Return response matching the schema
    return {
        "id": like.id,
        "user_id": like.owner_id,  # Map owner_id to user_id in response
        "story_id": like.story_id,
        "created_at": like.created_at if hasattr(like, 'created_at') else datetime.utcnow()
    }

# Storyga comment va stikerli comment qo'yish
@router.post(
    "/{story_id}/comment", 
    summary="Storyga comment va stiker qo'yish",
    operation_id="comment_story"
)
def comment_story(story_id: int, user_id: int = Form(...), text: str = Form(None), sticker_id: int = Form(None), db: Session = Depends(get_db)):
    # Create comment with owner_id instead of user_id
    comment = models.StoryComment(owner_id=user_id, story_id=story_id, text=text)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    # Return formatted response matching the schema
    return {
        "id": comment.id,
        "user_id": comment.owner_id,  # Map owner_id to user_id in response
        "story_id": comment.story_id,
        "text": comment.text,
        "created_at": comment.created_at.isoformat() if hasattr(comment, 'created_at') else datetime.utcnow().isoformat()
    }

# Storyga kim like bosganini ko'rish
@router.get("/{story_id}/likes", summary="Storyga kim like bosganini ko'rish")
def story_likes(story_id: int, db: Session = Depends(get_db)):
    likes = db.query(models.StoryLike).filter(models.StoryLike.story_id == story_id).all()
    # Map owner_id to user_id in the response to match the expected schema
    return [{"user_id": l.owner_id} for l in likes]

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
from typing import Optional

# StoryCreate class removed as we don't need it

@router.post(
    "/create", 
    summary="Create a new story",
    responses={
        201: {"description": "Story created successfully"},
        400: {"description": "Invalid input or missing required fields"},
        500: {"description": "Internal server error"}
    }
)
async def create_story(
    request: Request,
    user_id: int = Form(..., description="ID of the user creating the story"),
    text: str = Form("", description="Optional text content for the story"),
    media: Optional[UploadFile] = File(None, description="Media file (image or video) for the story (max 50MB)"),
    db: Session = Depends(get_db)
):
    """
    Create a new story.
    All fields are optional. A story can be created with just the user_id.
    If both image and video are provided, video will be used.
    """
    # Process media upload (if provided)
    file_path = None
    media_path = None
    
    try:
        if media and hasattr(media, 'filename') and media.filename:
            # Ensure upload directory exists
            os.makedirs(STORY_UPLOAD_DIR, exist_ok=True)
            
            # Get file info
            file_ext = os.path.splitext(media.filename.lower())[1]
            content_type = media.content_type or ''
            
            # Validate file type
            is_image = content_type.startswith('image/') or file_ext in ['.jpg', '.jpeg', '.png', '.gif']
            is_video = content_type.startswith('video/') or file_ext in ['.mp4', '.mov', '.avi', '.mkv']
            
            if not (is_image or is_video):
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "detail": "Noto'g'ri fayl formati. Ruxsat etilgan formatlar: JPG, JPEG, PNG, GIF, MP4, MOV, AVI, MKV"}
                )
            
            # Generate unique filename
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"story_{timestamp}_{media.filename}"
            media_path = os.path.join(STORY_UPLOAD_DIR, filename)
            
            # Save the file
            with open(media_path, "wb") as buffer:
                shutil.copyfileobj(media.file, buffer)
            
            # Prepare media info
            media_type = "image" if is_image else "video"
            file_path = {
                'url': str(media_path),
                'type': media_type,
                'created_at': datetime.utcnow().isoformat()
            }
            
            if is_video:
                file_path['duration'] = 0  # Can be extracted from video if needed
                file_path['thumbnail'] = None  # Can generate thumbnail if needed
                
    except Exception as e:
        # Clean up any partially uploaded file
        if media_path and os.path.exists(media_path):
            try:
                os.remove(media_path)
            except:
                pass
                
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": f"Faylni yuklashda xatolik: {str(e)}"}
        )
    finally:
        # Ensure file is closed
        if media and hasattr(media, 'file'):
            try:
                media.file.close()
            except:
                pass
    try:
        # Clean text if provided
        text = text.strip() if (text and isinstance(text, str)) else ""
        
        # Validate user_id
        try:
            user_id = int(user_id) if user_id else None
        except (ValueError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": "Noto'g'ri user_id formati"}
            )
            
        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "detail": "user_id kiritilishi shart"}
            )
        
        # Process @mentions in the text if text exists
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
        
        # Handle file path if media was uploaded
        if file_path:
            file_path = str(file_path)
        # No need to set file_path or media_type to None as they're already None by default
        
        try:
            # Create story with only the provided fields
            story_data = {
                "owner_id": user_id,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=24)
            }
            
            # Add media information to story data if any media was provided
            if file_path:
                # Store the media information as JSON in the database
                story_data["media_url"] = json.dumps(file_path, ensure_ascii=False)
            else:
                # No media - set to null in the database
                story_data["media_url"] = None
            
            # Clean and store text if provided (in response only, not in DB)
            text = text.strip() if text and isinstance(text, str) else ""
            
            # Create and save the story
            db_story = models.Story(**story_data)
            db.add(db_story)
            db.flush()
            
            # Create notifications for mentioned users
            if mentioned_users:
                # Get the user who created the story
                creator = db.query(models.User).filter(models.User.id == user_id).first()
                username = creator.username if creator else "Someone"
                
                for user_id in mentioned_users:
                    notification = models.Notification(
                        user_id=user_id,
                        type='mention',
                        content=f"You were mentioned in a story by {username}",
                        is_read=False
                    )
                    db.add(notification)
            
            db.commit()
            db.refresh(db_story)
            
            # Get user info for response
            user = db.query(models.User).filter(models.User.id == user_id).first()
            
            # Prepare response data
            response_data = {
                "id": db_story.id,
                "user_id": db_story.owner_id,
                "user_name": user.username if user else "Unknown",
                "user_avatar": user.avatar_url if user and hasattr(user, 'avatar_url') else None,
                "text": text,  # Return the text in the response (not stored in DB)
                "media": json.loads(db_story.media_url) if db_story.media_url else None,
                "media_type": media_type if db_story.media_url else None,
                "created_at": db_story.created_at.isoformat(),
                "expires_at": db_story.expires_at.isoformat() if db_story.expires_at else None,
                "likes_count": 0,
                "comments_count": 0,
                "is_owner": True,
                "is_liked": False
            }
            
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "Story created successfully",
                    "data": response_data
                }
            )
            
        except Exception as e:
            db.rollback()
            # Clean up uploaded file if there was an error
            if 'file_path' in locals() and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "detail": f"Error creating story: {str(e)}"
                }
            )
        
    except Exception as e:
        # Clean up file if there was an error
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        if 'db' in locals():
            db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": f"Unexpected error: {str(e)}"
            }
        )

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
    current_user_id: Optional[int] = Query(
        None, 
        description="Current user's ID for checking ownership and likes"
    ),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    try:
        # Base query
        query = db.query(models.Story)\
            .options(joinedload(models.Story.owner))\
            .order_by(models.Story.created_at.desc())
        
        # Filter by user_id if provided
        if user_id:
            query = query.filter(models.Story.owner_id == int(user_id))
        
        # Execute query
        stories = query.all()
        
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
                "user_name": story.owner.username if story.owner else "Unknown",
                "user_avatar": story.owner.avatar if story.owner and hasattr(story.owner, 'avatar') else None,
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
            if current_user_id and str(story.owner_id) == str(current_user_id):
                story_data["is_owner"] = True
                
            # Check if current user liked this story
            if current_user_id and any(like.owner_id == int(current_user_id) for like in story.likes):
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
    summary="Delete a story (owner only)",
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
    user_id: int = Query(..., description="ID of the user trying to delete the story"),
    db: Session = Depends(get_db)
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
        
        # Check if user is the story owner
        if story.owner_id != user_id:
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
