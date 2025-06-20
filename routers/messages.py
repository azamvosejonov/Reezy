import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi.responses import JSONResponse
from typing import List, Optional, Union
from datetime import datetime
import json

import models, schemas
from database import get_db
from utils.file_utils import save_upload_file, delete_file, MAX_FILE_SIZE, SUPPORTED_FILE_TYPES
from services.block_service import BlockService
from models.user import User
from .auth import get_current_user

router = APIRouter()

@router.post("/send", response_model=schemas.Message, summary="Xabar yuborish")
async def send_message(
    from_user_id: int, 
    to_user_id: int, 
    text: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify that the current user is the sender
    if current_user.id != from_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz boshqa foydalanuvchi nomidan xabar yubora olmaysiz"
        )
    # Create BlockService instance
    block_service = BlockService(db)
    
    # Check if users have blocked each other in either direction
    is_blocked = await block_service.check_block_status(from_user_id, to_user_id)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu foydalanuvchiga xabar yubora olmaysiz. Foydalanuvchi sizni bloklagan yoki siz uni bloklagansiz."
        )
        
    # Check if recipient has blocked the sender
    is_recipient_blocked = await block_service.check_block_status(to_user_id, from_user_id)
    if is_recipient_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu foydalanuvchiga xabar yubora olmaysiz. Foydalanuvchi sizni bloklagan yoki siz uni bloklagansiz."
        )
    
    # Create the message
    new_msg = models.Message(
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        content=text,
        is_read=False,
        deleted_for_sender=False,
        deleted_for_recipient=False
    )
    
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    
    # Get sender and recipient info with a single query for better performance
    users = db.query(models.User).filter(
        models.User.id.in_([from_user_id, to_user_id])
    ).all()
    
    sender = next((u for u in users if u.id == from_user_id), None)
    recipient = next((u for u in users if u.id == to_user_id), None)
    
    if not sender or not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi"
        )
    
    # Format the response according to the Message schema
    response = {
        "id": new_msg.id,
        "content": new_msg.content,
        "message_type": "text",
        "sender_id": new_msg.from_user_id,
        "recipient_id": new_msg.to_user_id,
        "conversation_id": f"{min(from_user_id, to_user_id)}_{max(from_user_id, to_user_id)}",
        "is_read": new_msg.is_read,
        "is_edited": False,
        "created_at": new_msg.created_at.isoformat(),
        "updated_at": new_msg.created_at.isoformat(),  # Use created_at since we don't have updated_at
        "deleted_at": None,
        "sender": {
            "id": sender.id,
            "username": sender.username,
            "full_name": sender.full_name,
            "avatar_url": getattr(sender, 'avatar_url', None) or getattr(sender, 'profile_picture', None)
        },
        "recipient": {
            "id": recipient.id,
            "username": recipient.username,
            "full_name": recipient.full_name,
            "avatar_url": getattr(recipient, 'avatar_url', None) or getattr(recipient, 'profile_picture', None)
        },
        "parent_message": None,
        "reply_to": None,
        "attachments": [
            {
                "id": att.id,
                "file_url": att.file_url,
                "file_type": att.file_type,
                "file_name": att.file_name,
                "file_size": att.file_size,
                "created_at": att.created_at.isoformat()
            } for att in getattr(new_msg, 'attachments', [])
        ]
    }
    
    return response

@router.get("/inbox/{user_id}", response_model=List[schemas.Message])
async def get_inbox(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify that the current user is requesting their own inbox
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz boshqa foydalanuvchining xabarlarini ko'rolmaysiz"
        )
    # Get all messages for the user
    messages = db.query(models.Message).filter(
        models.Message.to_user_id == user_id
    ).order_by(models.Message.created_at.desc()).all()
    
    if not messages:
        return []
    
    # Get all unique user IDs involved in the messages
    user_ids = set()
    for msg in messages:
        user_ids.add(msg.from_user_id)
        user_ids.add(msg.to_user_id)
    
    # Get all users in a single query
    users = {user.id: user for user in db.query(models.User).filter(models.User.id.in_(user_ids)).all()}
    
    # Format the response
    formatted_messages = []
    for msg in messages:
        sender = users.get(msg.from_user_id)
        recipient = users.get(msg.to_user_id)
        
        if not sender or not recipient:
            continue  # Skip if user not found
            
        formatted_messages.append({
            "id": msg.id,
            "content": msg.content,
            "message_type": "text",
            "sender_id": msg.from_user_id,
            "conversation_id": f"{min(msg.from_user_id, msg.to_user_id)}_{max(msg.from_user_id, msg.to_user_id)}",
            "is_read": msg.is_read,
            "is_edited": False,
            "created_at": msg.created_at,
            "updated_at": msg.created_at,  # Use created_at since we don't have updated_at
            "deleted_at": None,
            "sender": {
                "id": sender.id,
                "username": sender.username,
                "profile_picture": getattr(sender, 'profile_picture', None),
                "full_name": getattr(sender, 'full_name', "")
            },
            "recipient": {
                "id": recipient.id,
                "username": recipient.username,
                "profile_picture": getattr(recipient, 'profile_picture', None),
                "full_name": getattr(recipient, 'full_name', "")
            },
            "parent_message": None,
            "reply_to": None,
            "attachments": []
        })
    
    return formatted_messages

@router.get("/dialog/{user1_id}/{user2_id}", response_model=List[schemas.Message], summary="Ikkita foydalanuvchi o'rtasidagi chat")
async def get_dialog(
    user1_id: int, 
    user2_id: int, 
    show_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify that the current user is one of the participants
    if current_user.id not in (user1_id, user2_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu suhbatni ko'rish huquqiga egasiz"  # You are not authorized to view this conversation
        )
    # Build the base query
    query = db.query(models.Message).filter(
        or_(
            and_(models.Message.from_user_id == user1_id, models.Message.to_user_id == user2_id),
            and_(models.Message.from_user_id == user2_id, models.Message.to_user_id == user1_id)
        )
    )
    
    # Apply deleted message filtering
    if not show_deleted:
        query = query.filter(
            ~models.Message.deleted_for_sender,
            ~models.Message.deleted_for_recipient
        )
    
    # Get messages
    messages = query.order_by(models.Message.created_at).all()
    
    if not messages:
        return []
    
    # Get all unique user IDs
    user_ids = {user1_id, user2_id}
    
    # Get all users in a single query
    users = {user.id: user for user in db.query(models.User).filter(
        models.User.id.in_(user_ids)
    ).all()}
    
    # Format the response
    formatted_messages = []
    for msg in messages:
        sender = users.get(msg.from_user_id)
        recipient = users.get(msg.to_user_id)
        
        if not sender or not recipient:
            continue  # Skip if user not found
            
        formatted_messages.append({
            "id": msg.id,
            "content": msg.content,
            "message_type": "text",
            "sender_id": msg.from_user_id,
            "conversation_id": f"{min(user1_id, user2_id)}_{max(user1_id, user2_id)}",
            "is_read": msg.is_read,
            "is_edited": False,
            "created_at": msg.created_at,
            "updated_at": msg.created_at,  # Use created_at since we don't have updated_at
            "deleted_at": None,
            "sender": {
                "id": sender.id,
                "username": sender.username,
                "profile_picture": getattr(sender, 'profile_picture', None),
                "full_name": getattr(sender, 'full_name', "")
            },
            "recipient": {
                "id": recipient.id,
                "username": recipient.username,
                "profile_picture": getattr(recipient, 'profile_picture', None),
                "full_name": getattr(recipient, 'full_name', "")
            },
            "parent_message": None,
            "reply_to": None,
            "attachments": []
        })
    
    return formatted_messages

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Bitta xabarni o'chirish")
def delete_message(
    message_id: int,
    user_id: int,  # Current user ID to determine if they're sender or recipient
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify the current user matches the user_id parameter
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Noto'g'ri foydalanuvchi"
        )
    message = db.query(models.Message).filter(models.Message.id == message_id).first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Xabar topilmadi"
        )
    
    # Check if user is the sender or recipient
    if user_id == message.from_user_id:
        message.deleted_for_sender = True
    elif user_id == message.to_user_id:
        message.deleted_for_recipient = True
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu xabarni o'chira olmaysiz"
        )
    
    # If both sides have deleted the message, delete it completely
    if message.deleted_for_sender and message.deleted_for_recipient:
        db.delete(message)
    
    db.commit()
    return {"message": "Xabar o'chirildi"}

@router.delete("/clear-chat/{user1_id}/{user2_id}", summary="Barcha xabarlarni o'chirish")
def clear_chat(
    user1_id: int,
    user2_id: int,
    current_user_id: int,  # The user who is requesting the deletion
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify the current user matches the current_user_id parameter
    if current_user.id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Noto'g'ri foydalanuvchi"
        )
    # Verify current user is part of the conversation
    if current_user_id not in (user1_id, user2_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu suhbatni tozalash huquqiga egasiz"
        )
    
    # Mark messages as deleted for the current user
    messages = db.query(models.Message).filter(
        or_(
            and_(
                models.Message.from_user_id == user1_id,
                models.Message.to_user_id == user2_id
            ),
            and_(
                models.Message.from_user_id == user2_id,
                models.Message.to_user_id == user1_id
            )
        )
    ).all()
    
    for msg in messages:
        if current_user_id == msg.from_user_id:
            msg.deleted_for_sender = True
        elif current_user_id == msg.to_user_id:
            msg.deleted_for_recipient = True
            
        # Delete completely if both sides have deleted
        if msg.deleted_for_sender and msg.deleted_for_recipient:
            db.delete(msg)
    
    db.commit()
    return {"message": "Barcha xabarlar o'chirildi"}

@router.delete("/delete-conversation/{user1_id}/{user2_id}", summary="Suhbatni butunlay o'chirish")
def delete_conversation(
    user1_id: int,
    user2_id: int,
    current_user_id: int,  # The user who is requesting the deletion
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify the current user matches the current_user_id parameter
    if current_user.id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Noto'g'ri foydalanuvchi"
        )
    # Verify current user is part of the conversation
    if current_user_id not in (user1_id, user2_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Siz bu suhbatni o'chirish huquqiga egasiz"
        )
    
    # Delete all messages between users
    db.query(models.Message).filter(
        or_(
            and_(
                models.Message.from_user_id == user1_id,
                models.Message.to_user_id == user2_id
            ),
            and_(
                models.Message.from_user_id == user2_id,
                models.Message.to_user_id == user1_id
            )
        )
    ).delete(synchronize_session=False)
    
    db.commit()
    return {"message": "Suhbat muvaffaqiyatli o'chirildi"}
