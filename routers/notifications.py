from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List


import schemas, models
from database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[schemas.Notification])
def get_notifications(
    user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    # Get notifications for the current user with actor information
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    ).order_by(models.Notification.created_at.desc()).all()
    
    # Format the response to match the Notification schema
    result = []
    for notif in notifications:
        # Get actor info (simplified - in a real app, join with users table)
        actor = {
            "id": notif.actor_id,
            "username": "user" + str(notif.actor_id),  # Placeholder
            "profile_picture": None
        }
        
        # Format the notification
        result.append({
            "id": notif.id,
            "type": notif.type,
            "message": notif.content or "",
            "is_read": notif.is_read,
            "user_id": notif.user_id,
            "actor_id": notif.actor_id,
            "reference_id": notif.reference_id,
            "reference_type": notif.reference_type,
            "created_at": notif.created_at,
            "updated_at": notif.updated_at or notif.created_at,
            "actor": actor
        })
    
    return result
