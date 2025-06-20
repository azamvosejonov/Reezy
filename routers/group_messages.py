import os
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Union
from datetime import datetime
import json

import models, schemas
from schemas import group as group_schemas
from database import SessionLocal, get_db
from utils.file_utils import save_upload_file, MAX_FILE_SIZE, SUPPORTED_FILE_TYPES
from routers.auth import get_current_user

router = APIRouter(prefix="/api/groups")

async def process_group_attachments(
    files: List[UploadFile], 
    db: Session,
    message_id: int
) -> List[models.MessageAttachment]:
    """Process and save group message attachments."""
    attachments = []
    for file in files:
        try:
            # Save the uploaded file
            file_info = await save_upload_file(file)
            
            # Create attachment record
            attachment = models.MessageAttachment(
                message_id=message_id,
                file_url=file_info["file_url"],
                file_type=file_info["message_type"].value,
                file_name=file_info["file_name"],
                file_size=file_info["file_size"]
            )
            db.add(attachment)
            attachments.append(attachment)
            
        except Exception as e:
            # Log the error and continue with other files
            print(f"Error processing file {file.filename}: {str(e)}")
    
    return attachments

# Create a new group
@router.post("/", response_model=group_schemas.GroupInDB, status_code=status.HTTP_201_CREATED)
def create_group(group: group_schemas.GroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Create a new group.
    The creator automatically becomes the group admin and member.
    """
    # Create the group
    db_group = models.Group(
        name=group.name,
        description=group.description,
        creator_id=current_user.id,
        image=group.image
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    
    # Add creator as group admin
    admin = models.GroupAdmin(
        group_id=db_group.id,
        user_id=group.creator_id
    )
    db.add(admin)
    
    # Add creator as member
    member = models.GroupMember(
        group_id=db_group.id,
        user_id=group.creator_id
    )
    db.add(member)
    
    db.commit()
    db.refresh(db_group)
    return db_group

# Delete a group (creator only)
@router.delete("/{group_id}", status_code=status.HTTP_200_OK)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Delete a group.
    Only the group creator can delete the group.
    This will also delete all messages and memberships.
    """
    # Get the group with creator information
    group = db.query(models.Group).filter(
        models.Group.id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if current user is the group creator
    if group.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group creator can delete the group"
        )
    
    # Delete group messages
    db.query(models.GroupMessage).filter(
        models.GroupMessage.group_id == group_id
    ).delete()
    
    # Delete group admins
    db.query(models.GroupAdmin).filter(
        models.GroupAdmin.group_id == group_id
    ).delete()
    
    # Delete group members
    db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id
    ).delete()
    
    # Finally, delete the group
    db.delete(group)
    db.commit()
    
    return {"message": "Group deleted successfully"}

# Send message to group
@router.post("/{group_id}/messages", response_model=schemas.Message)
async def send_group_message(
    group_id: int,
    content: Optional[str] = Form(None),
    files: List[UploadFile] = File([], media_type='multipart/form-data'),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Handle empty file list from form data
    files = [f for f in files if f and (hasattr(f, 'filename') and f.filename)]
    # Check if message has any content (either text or files)
    if not content and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message must have either content or files"
        )
        
    # Set default message type to text if no files are present
    if not files and not content:
        content = ""  # Empty string for text-only messages
    
    # Check if current user is a member of the group
    membership = db.query(models.GroupMember).filter(
        and_(
            models.GroupMember.group_id == group_id,
            models.GroupMember.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a group member to post messages"
        )
    
    # Determine message type
    message_type = schemas.MessageType.TEXT
    if files:
        if len(files) == 1:
            # If single file, use the file's message type
            file_ext = files[0].filename.split('.')[-1].lower() if '.' in files[0].filename else ''
            for file_type in SUPPORTED_FILE_TYPES.values():
                if file_ext in file_type["extensions"]:
                    message_type = file_type["message_type"]
                    break
        else:
            # For multiple files, use generic file type
            message_type = schemas.MessageType.FILE
    
    # Create the message
    db_message = models.GroupMessage(
        content=content,
        user_id=current_user.id,
        group_id=group_id,
        message_type=message_type.value
    )
    
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    # Process attachments if any
    if files:
        attachments = await process_group_attachments(files, db, db_message.id)
        db.commit()
    
    # Get current user info for response
    user = current_user
    
    # Format the response
    response = {
        "id": db_message.id,
        "content": db_message.content,
        "message_type": message_type.value,
        "sender_id": current_user.id,
        "group_id": group_id,
        "is_read": False,
        "is_edited": False,
        "created_at": db_message.created_at.isoformat(),
        "updated_at": db_message.created_at.isoformat(),
        "deleted_at": None,
        "sender": {
            "id": current_user.id,
            "username": current_user.username,
            "full_name": current_user.full_name,
            "avatar_url": current_user.avatar_url
        },
        "attachments": [
            {
                "id": att.id,
                "file_url": att.file_url,
                "file_type": att.file_type,
                "file_name": att.file_name,
                "file_size": att.file_size,
                "created_at": att.created_at.isoformat()
            } for att in getattr(db_message, 'attachments', [])
        ]
    }
    
    return response

# Get group messages
@router.get("/{group_id}/messages", response_model=List[schemas.Message])
def get_group_messages(
    group_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if user is a member of the group
    membership = db.query(models.GroupMember).filter(
        and_(
            models.GroupMember.group_id == group_id,
            models.GroupMember.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a group member to view messages"
        )
    
    # Get messages with user relationship
    messages = db.query(models.GroupMessage).filter(
        models.GroupMessage.group_id == group_id
    ).order_by(
        models.GroupMessage.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return messages

# Delete a single message
@router.delete("/{group_id}/messages/{message_id}", status_code=status.HTTP_200_OK)
def delete_group_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Delete a message from the group.
    Any group member can delete their own messages.
    """
    # Get the message with group information
    message = db.query(models.GroupMessage).filter(
        models.GroupMessage.id == message_id,
        models.GroupMessage.user_id == current_user.id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Delete the message
    db.delete(message)
    db.commit()
    
    return {"message": "Message deleted successfully"}

# Clear all messages from group (creator only)
@router.delete("/{group_id}/clear-messages", status_code=status.HTTP_200_OK)
def clear_group_messages(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Clear all messages from a group.
    Only the group creator can clear all messages.
    """
    # Get the group with creator information
    group = db.query(models.Group).filter(
        models.Group.id == group_id
    ).first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if current user is the group creator
    if group.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group creator can clear all messages"
        )
    
    # Delete all messages
    db.query(models.GroupMessage).filter(
        models.GroupMessage.group_id == group_id
    ).delete()
    
    db.commit()
    return {"message": "All messages have been cleared"}
