from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

import schemas, models
from database import SessionLocal
from models.user import User
from .auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[schemas.Notification])
async def get_notifications(
    user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify that the authenticated user is requesting their own notifications
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own notifications"
        )
    # Get notifications for the current user
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    ).order_by(models.Notification.created_at.desc()).all()
    
    # Format the response to match the Notification schema
    result = []
    for notif in notifications:
        # Default values
        actor_id = 0  # Default system user ID
        username = "System"
        
        # Try to extract actor information from the notification content
        if notif.content:
            if "@" in notif.content:
                # If content has @username format, try to extract username
                parts = notif.content.split("@")
                if len(parts) > 1:
                    username = "@" + parts[1].split()[0] if parts[1].strip() else username
            
            # Try to find a user ID in the content (e.g., "User 123 liked your post")
            import re
            id_match = re.search(r'user (\d+)', notif.content.lower())
            if id_match:
                try:
                    actor_id = int(id_match.group(1))
                except (ValueError, IndexError):
                    pass
        
        # Create actor object with valid ID
        actor = {
            "id": actor_id,
            "username": username,
            "profile_picture": None
        }
        
        # Format the notification according to the schema
        notification_data = {
            "id": notif.id,
            "type": notif.type or "system",
            "message": notif.content or "",
            "is_read": notif.is_read,
            "user_id": notif.user_id,
            "actor_id": actor_id,  # Now always an integer
            "reference_id": None,  # Not available in the current model
            "reference_type": None,  # Not available in the current model
            "created_at": notif.created_at,
            "updated_at": notif.created_at,  # Use created_at since updated_at doesn't exist
            "actor": actor
        }
        
        result.append(notification_data)
    
    return result
