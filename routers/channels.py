import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, UploadFile, File, Form
from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

import models, schemas
from schemas import channel_message as channel_message_schemas
from schemas.message import MessageType
from utils.file_utils import save_upload_file, SUPPORTED_FILE_TYPES
from database import get_db

router = APIRouter(prefix="/api/channels", tags=["channels"])

# Search channels by name or description

async def process_channel_attachments(
    files: List[UploadFile], 
    db: Session,
    message_id: int
) -> List[models.MessageAttachment]:
    """Process and save channel message attachments."""
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

# Create a new channel
@router.post("/", response_model=schemas.ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(channel: schemas.ChannelCreate, db: Session = Depends(get_db)):
    """
    Create a new channel.
    Only the creator can post messages to the channel.
    """
    # Check if channel name already exists
    existing_channel = db.query(models.Channel).filter(
        models.Channel.name == channel.name
    ).first()
    
    if existing_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel with this name already exists"
        )
    
    # Get creator user first to include in response
    creator = db.query(models.User).filter(
        models.User.id == channel.creator_id
    ).first()
    
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator user not found"
        )
    
    try:
        db_channel = models.Channel(
            name=channel.name,
            description=channel.description,
            image=channel.image,
            creator_id=channel.creator_id,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        db.add(db_channel)
        db.commit()
        db.refresh(db_channel)
        
        # Auto-subscribe the creator
        subscribe_channel(db_channel.id, channel.creator_id, db)
        
        # Format the response according to ChannelResponse schema
        response = {
            "id": db_channel.id,
            "name": db_channel.name,
            "description": db_channel.description,
            "image": db_channel.image,
            "creator_id": db_channel.creator_id,
            "created_at": db_channel.created_at,
            "is_active": db_channel.is_active,
            "creator": {
                "id": creator.id,
                "username": creator.username,
                "profile_picture": getattr(creator, 'profile_picture', None),
                "full_name": getattr(creator, 'full_name', "")
            },
            "subscriber_count": 1,  # Creator is auto-subscribed
            "message_count": 0,
            "is_subscribed": True
        }
        
        return response
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating channel: {str(e)}"
        )

# Subscribe to a channel
@router.post("/{channel_id}/subscribe/{user_id}", status_code=status.HTTP_200_OK)
def subscribe_channel(
    channel_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Subscribe a user to a channel.
    """
    # Check if subscription already exists
    existing_sub = db.query(models.ChannelSubscriber).filter(
        and_(
            models.ChannelSubscriber.channel_id == channel_id,
            models.ChannelSubscriber.user_id == user_id
        )
    ).first()
    
    if existing_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already subscribed to this channel"
        )
    
    # Create new subscription
    subscription = models.ChannelSubscriber(
        channel_id=channel_id,
        user_id=user_id,
        subscribed_at=datetime.utcnow()
    )
    
    db.add(subscription)
    db.commit()
    
    return {"message": "Successfully subscribed to the channel"}

# Post a message to channel (creator only)
@router.post("/{channel_id}/messages", response_model=channel_message_schemas.ChannelMessage, status_code=status.HTTP_201_CREATED)
async def create_channel_message(
    channel_id: int,
    text: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    from_user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """
    Create a new message in a channel.
    
    - **text**: Message text (optional if files are provided)
    - **files**: List of files to attach (optional)
    - **from_user_id**: ID of the user sending the message
    """
    # Check if message has content or files
    if not text and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message must have either text or files"
        )
    
    # Check if user is a subscriber
    subscription = db.query(models.ChannelSubscriber).filter(
        and_(
            models.ChannelSubscriber.channel_id == channel_id,
            models.ChannelSubscriber.user_id == from_user_id
        )
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only subscribers can post messages in this channel"
        )
    
    # Check if channel exists and is active
    channel = db.query(models.Channel).filter(
        and_(
            models.Channel.id == channel_id,
            models.Channel.is_active == True
        )
    ).first()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found or inactive"
        )
    
    # Determine message type
    message_type = MessageType.TEXT
    if files:
        if len(files) == 1:
            # If single file, use the file's message type
            file_ext = os.path.splitext(files[0].filename)[1].lower()
            for file_type in SUPPORTED_FILE_TYPES.values():
                if file_ext in file_type["extensions"]:
                    message_type = file_type["message_type"]
                    break
        else:
            # For multiple files, use generic file type
            message_type = MessageType.FILE
    
    # Create the message
    db_message = models.ChannelMessage(
        text=text,
        message_type=message_type,
        from_user_id=from_user_id,
        channel_id=channel_id
    )
    
    db.add(db_message)
    db.flush()  # Flush to get the message ID
    
    # Process attachments if any
    if files:
        attachments = await process_channel_attachments(files, db, db_message.id)
    
    db.commit()
    db.refresh(db_message)
    
    # Get the message with relationships loaded
    message = (db.query(models.ChannelMessage)
        .options(
            selectinload(models.ChannelMessage.attachments),
            selectinload(models.ChannelMessage.user)
        )
        .filter(models.ChannelMessage.id == db_message.id)
        .first())
    
    # Format the response
    return {
        **message.__dict__,
        "sender": {
            "id": message.user.id,
            "username": message.user.username,
            "full_name": message.user.full_name,
            "avatar_url": message.user.avatar_url
        },
        "attachments": [
            {
                "id": att.id,
                "file_url": att.file_url,
                "file_type": att.file_type,
                "file_name": att.file_name,
                "file_size": att.file_size,
                "created_at": att.created_at.isoformat()
            } for att in message.attachments
        ]
    }

# Get channel messages (subscribers only)
@router.get("/{channel_id}/messages", response_model=List[channel_message_schemas.ChannelMessage])
async def get_channel_messages(
    channel_id: int,
    current_user_id: int = Query(..., description="Current user's ID"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get messages from a channel.
    Only channel subscribers can view messages.
    """
    # Check if channel exists and is active
    channel = db.query(models.Channel).filter(
        and_(
            models.Channel.id == channel_id,
            models.Channel.is_active == True
        )
    ).first()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found or inactive"
        )
    
    # Check if user is a subscriber
    subscription = db.query(models.ChannelSubscriber).filter(
        and_(
            models.ChannelSubscriber.channel_id == channel_id,
            models.ChannelSubscriber.user_id == current_user_id
        )
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only subscribers can view channel messages"
        )
    
    # Get messages with relationships
    messages = (db.query(models.ChannelMessage)
        .options(
            selectinload(models.ChannelMessage.attachments),
            selectinload(models.ChannelMessage.user)
        )
        .filter(models.ChannelMessage.channel_id == channel_id)
        .order_by(models.ChannelMessage.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all())
    
    # Format response
    response = []
    for msg in messages:
        message_data = {
            **msg.__dict__,
            "sender": {
                "id": msg.user.id,
                "username": msg.user.username,
                "full_name": msg.user.full_name,
                "avatar_url": msg.user.avatar_url
            },
            "attachments": [
                {
                    "id": att.id,
                    "file_url": att.file_url,
                    "file_type": att.file_type,
                    "file_name": att.file_name,
                    "file_size": att.file_size,
                    "created_at": att.created_at.isoformat()
                } for att in msg.attachments
            ]
        }
        response.append(message_data)
    
    return response

# Add a comment to a channel message (subscribers only)
@router.post("/messages/{message_id}/comments", response_model=schemas.ChannelMessageResponse, status_code=status.HTTP_201_CREATED)
def add_comment_to_message(
    message_id: int,
    comment: schemas.ChannelMessageCreate,  # Using same schema for messages and comments
    user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    """
    Add a comment to a channel message.
    Only channel subscribers can comment.
    """
    # Get the message with channel info
    message = db.query(models.ChannelMessage).join(
        models.Channel,
        models.Channel.id == models.ChannelMessage.channel_id
    ).filter(
        models.ChannelMessage.id == message_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user is subscribed to the channel
    is_subscribed = db.query(models.ChannelSubscriber).filter(
        and_(
            models.ChannelSubscriber.channel_id == message.channel_id,
            models.ChannelSubscriber.user_id == user_id
        )
    ).first()
    
    if not is_subscribed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be subscribed to comment on messages"
        )
    
    # Create and save the comment
    db_comment = models.ChannelComment(
        message_id=message_id,
        user_id=user_id,
        text=comment.text,
        created_at=datetime.utcnow()
    )
    
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    return db_comment

# Delete a channel (creator only)
@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int,
    user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    """
    Delete a channel and all its messages and comments.
    Only the channel creator can delete the channel.
    """
    # Get the channel
    channel = db.query(models.Channel).filter(
        models.Channel.id == channel_id
    ).first()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Check if user is the channel creator
    if channel.creator_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the channel creator can delete the channel"
        )
    
    # Create a subquery for message IDs in this channel
    message_subquery = select(models.ChannelMessage.id).where(
        models.ChannelMessage.channel_id == channel_id
    ).scalar_subquery()
    
    # Delete all comments for messages in this channel
    db.query(models.ChannelComment).filter(
        models.ChannelComment.message_id.in_(message_subquery)
    ).delete(synchronize_session=False)
    
    # Delete all messages
    db.query(models.ChannelMessage).filter(
        models.ChannelMessage.channel_id == channel_id
    ).delete(synchronize_session=False)
    
    # Delete all subscriptions
    db.query(models.ChannelSubscriber).filter(
        models.ChannelSubscriber.channel_id == channel_id
    ).delete(synchronize_session=False)
    
    # Finally, delete the channel
    db.delete(channel)
    db.commit()
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Delete a single message (creator only)
@router.delete("/{channel_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel_message(
    channel_id: int,
    message_id: int,
    user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    """
    Delete a message from a channel.
    Only the channel creator can delete messages.
    """
    # Get the message with relationships loaded
    message = (db.query(models.ChannelMessage)
        .options(
            selectinload(models.ChannelMessage.attachments),
            selectinload(models.ChannelMessage.user)
        )
        .filter(models.ChannelMessage.id == message_id)
        .first())
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in this channel"
        )
        
    if not message.channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Check if user is the channel creator
    if message.channel.creator_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the channel creator can delete messages"
        )
    
    try:
        # First delete all comments on this message
        db.query(models.ChannelComment).filter(
            models.ChannelComment.message_id == message_id
        ).delete(synchronize_session=False)
        
        # Then delete the message
        db.delete(message)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting message: {str(e)}"
        )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Clear all messages in a channel (creator only)
@router.delete("/{channel_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
def clear_channel_messages(
    channel_id: int,
    user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    """
    Clear all messages in a channel.
    Only the channel creator can clear messages.
    """
    # Get the channel
    channel = db.query(models.Channel).filter(
        models.Channel.id == channel_id
    ).first()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Check if user is the channel creator
    if channel.creator_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the channel creator can clear messages"
        )
    
    # Delete all messages in the channel
    db.query(models.ChannelMessage).filter(
        models.ChannelMessage.channel_id == channel_id
    ).delete(synchronize_session=False)
    
    db.commit()
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Get comments for a message (subscribers only)
@router.get("/messages/{message_id}/comments", response_model=List[schemas.ChannelMessageResponse])
def get_message_comments(
    message_id: int,
    user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    """
    Get comments for a channel message.
    Only channel subscribers can view comments.
    """
    # Get the message with channel info
    message = db.query(models.ChannelMessage).join(
        models.Channel,
        models.Channel.id == models.ChannelMessage.channel_id
    ).filter(
        models.ChannelMessage.id == message_id
    ).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    # Check if user is subscribed to the channel
    is_subscribed = db.query(models.ChannelSubscriber).filter(
        and_(
            models.ChannelSubscriber.channel_id == message.channel_id,
            models.ChannelSubscriber.user_id == user_id
        )
    ).first()
    
    if not is_subscribed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be subscribed to view comments"
        )
    
    # Get comments for a message with user data
    comments = db.query(
        models.ChannelComment,
        models.User
    ).join(
        models.User,
        models.ChannelComment.user_id == models.User.id
    ).filter(
        models.ChannelComment.message_id == message_id
    ).order_by(
        models.ChannelComment.created_at.asc()
    ).all()
    
    # Format the response to include user data
    response = []
    for comment, user in comments:
        comment_dict = comment.__dict__.copy()
        comment_dict['user'] = {
            'id': user.id,
            'username': user.username,
            'profile_picture': user.profile_picture
        }
        response.append(comment_dict)
    
    return response
