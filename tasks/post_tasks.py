import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from celery import shared_task
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
import shutil


from models.user import User
from config import settings
from database import SessionLocal
from models import Post, Notification

logger = logging.getLogger(__name__)

class PostCreateData(BaseModel):
    user_id: int
    body: Optional[str] = None
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    video_duration: Optional[int] = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@shared_task(bind=True, name="create_post_task")
def create_post_task(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Background task to create a new post with media processing.
    """
    db = next(get_db())
    try:
        # Validate input data
        post_data = PostCreateData(**post_data)
        
        # Create the post
        db_post = Post(
            user_id=post_data.user_id,
            body=post_data.body,
            image=post_data.image_path,
            video=post_data.video_path,
            video_duration=post_data.video_duration,
            created_at=datetime.utcnow()
        )
        
        db.add(db_post)
        db.flush()  # Get the post ID for notifications
        
        # Process mentions in post body
        if post_data.body:
            process_mentions.delay(post_data.body, db_post.id, post_data.user_id)
        
        db.commit()
        db.refresh(db_post)
        
        return {"status": "success", "post_id": db_post.id}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating post: {str(e)}")
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds
    finally:
        db.close()

@shared_task(name="process_mentions")
def process_mentions(text: str, post_id: int, author_id: int):
    """Process @mentions in post text and create notifications."""
    import re
    from sqlalchemy.orm import Session
    
    db = next(get_db())
    try:
        # Find all mentions (@username)
        mentions = set(re.findall(r'@(\w+)', text))
        
        if not mentions:
            return
            
        # Get mentioned users
        users = db.query(User).filter(
            User.username.in_(mentions),
            User.id != author_id  # Don't notify the post author
        ).all()
        
        # Create notifications
        for user in users:
            notification = Notification(
                user_id=user.id,
                type="mention",
                message=f"You were mentioned in a post",
                data={"post_id": post_id},
                created_at=datetime.utcnow()
            )
            db.add(notification)
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing mentions: {str(e)}")
    finally:
        db.close()

@shared_task(name="cleanup_old_media")
def cleanup_old_media():
    """Clean up old unused media files."""
    from datetime import datetime, timedelta
    import os
    
    # Get all media directories
    media_dirs = [
        settings.MEDIA_ROOT / "posts",
        settings.MEDIA_ROOT / "videos",
        settings.MEDIA_ROOT / "thumbnails"
    ]
    
    cutoff_time = datetime.now() - timedelta(days=7)  # Keep files newer than 7 days
    
    for media_dir in media_dirs:
        if not media_dir.exists():
            continue
            
        for root, dirs, files in os.walk(media_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_time < cutoff_time:
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error removing file {file_path}: {str(e)}")

@shared_task(name="generate_video_thumbnail")
def generate_video_thumbnail(video_path: str, output_path: str):
    """Generate a thumbnail from a video file."""
    try:
        import cv2
        import os
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Open the video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        # Read the first frame
        ret, frame = cap.read()
        if not ret:
            raise ValueError(f"Could not read video frame: {video_path}")
        
        # Save the frame as an image
        cv2.imwrite(output_path, frame)
        
        # Release the video capture object
        cap.release()
        
        return {"status": "success", "thumbnail_path": output_path}
        
    except Exception as e:
        logger.error(f"Error generating video thumbnail: {str(e)}")
        raise
