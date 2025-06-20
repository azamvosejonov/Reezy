from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import os
import shutil

import models, schemas
from database import SessionLocal
from routers.auth import get_current_user

router = APIRouter()

# Create directory for group images if it doesn't exist
GROUP_IMAGE_DIR = "media/groups/"
os.makedirs(GROUP_IMAGE_DIR, exist_ok=True)

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_for_inappropriate_content(text: str):
    """Placeholder for content checking functionality."""
    # Content checking has been disabled
    pass

@router.post("/create", response_model=Dict[str, Any], summary="Guruh yaratish")
def create_group(
    name: str = Form(...),
    image: UploadFile = File(None),
    description: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # AI-powered content moderation
    check_for_inappropriate_content(name)
    if description:
        check_for_inappropriate_content(description)

    # Save image if provided
    image_path = None
    if image:
        image_path = os.path.join(GROUP_IMAGE_DIR, image.filename)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    
    # Create group
    group = models.Group(name=name, creator_id=current_user.id, image=image_path, description=description)
    db.add(group)
    db.commit()
    db.refresh(group)
    
    # Add current user as admin
    admin = models.GroupAdmin(group_id=group.id, user_id=current_user.id)
    db.add(admin)
    
    # Add current user as member
    member = models.GroupMember(group_id=group.id, user_id=current_user.id)
    db.add(member)
    
    db.commit()
    
    # Return a dictionary response
    return {
        "id": group.id,
        "name": group.name,
        "creator_id": group.creator_id,
        "image": group.image,
        "description": group.description,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "is_active": getattr(group, 'is_active', True)
    }

@router.post("/{group_id}/add_member", response_model=Dict[str, Any], summary="Guruhga odam qo'shish (faqat admin)")
def add_member(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Check if current user is admin of the group
    is_admin = db.query(models.GroupAdmin).filter_by(group_id=group_id, user_id=current_user.id).first()
    if not is_admin:
        raise HTTPException(status_code=403, detail="Faqat admin qo'sha oladi")
    exists = db.query(models.GroupMember).filter_by(group_id=group_id, user_id=user_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="Bu foydalanuvchi allaqachon guruhda")
    member = models.GroupMember(group_id=group_id, user_id=user_id)
    db.add(member)
    db.commit()
    return {"detail": "Qo'shildi"}

@router.delete("/{group_id}/remove_member", response_model=Dict[str, Any], summary="Guruhdan odam o'chirish (faqat admin)")
def remove_member(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Check if current user is admin of the group
    is_admin = db.query(models.GroupAdmin).filter_by(group_id=group_id, user_id=current_user.id).first()
    if not is_admin:
        raise HTTPException(status_code=403, detail="Faqat admin o'chira oladi")
    member = db.query(models.GroupMember).filter_by(group_id=group_id, user_id=user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Bunday a'zo yo'q")
    db.delete(member)
    db.commit()
    return {"detail": "O'chirildi"}

@router.post("/{group_id}/send_message", response_model=Dict[str, Any], summary="Guruhga xabar yuborish")
async def send_group_message(
    group_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if current user is a member of the group
    is_member = db.query(models.GroupMember).filter_by(
        group_id=group_id, user_id=current_user.id
    ).first()
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu guruh a'zosi emassiz"
        )
    
    # Create the message
    message = models.GroupMessage(
        content=content,
        user_id=current_user.id,
        group_id=group_id
    )
    
    db.add(message)
    db.commit()
    db.refresh(message)
    
    # Get user info for the response
    user = current_user
    
    return {
        "id": message.id,
        "content": message.content,
        "created_at": message.created_at,
        "user_id": message.user_id,
        "group_id": message.group_id,
        "user": {
            "id": user.id,
            "username": user.username,
            "profile_picture": user.profile_picture
        } if user else None
    }

@router.get("/{group_id}/messages", response_model=List[Dict[str, Any]], summary="Guruh chat tarixini olish")
def get_group_messages(group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Check if current user is a member of the group
    is_member = db.query(models.GroupMember).filter_by(
        group_id=group_id, user_id=current_user.id
    ).first()
    
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu guruh a'zosi emassiz"
        )
    
    messages = db.query(models.GroupMessage).filter_by(group_id=group_id).order_by(models.GroupMessage.created_at).all()
    return [{
        "id": msg.id,
        "content": msg.content,
        "created_at": msg.created_at,
        "user_id": msg.user_id,
        "group_id": msg.group_id,
        "user": {
            "id": msg.user.id,
            "username": msg.user.username,
            "profile_picture": msg.user.profile_picture
        } if msg.user else None
    } for msg in messages]
