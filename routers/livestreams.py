from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query, Body, Path as PathParam, Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session, joinedload
from typing import List, Set, Optional, Dict, Any
import json
from datetime import datetime
from sqlalchemy import and_

import models, schemas
from database import SessionLocal
from schemas.livestream import (
    LiveStream, LiveStreamComment, LiveStreamCreate, LiveStreamUpdate,
    LiveStreamCommentCreate, LiveStreamCommentInDB, LiveStreamList
)

router = APIRouter(
    prefix="/livestreams",
    tags=["Livestreams"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)

# --- Response Models ---

class UserResponse(BaseModel):
    """User information in responses."""
    id: int
    username: str
    profile_picture: Optional[str] = None

class CommentResponse(LiveStreamComment):
    """Enhanced comment response model with additional metadata."""
    user: UserResponse = Field(..., description="User who posted the comment")
    is_owner: bool = Field(..., description="Whether the current user is the comment author")
    can_delete: bool = Field(..., description="Whether the current user can delete this comment")
    
    model_config = ConfigDict(from_attributes=True)  # For Pydantic v2

class LikeResponse(BaseModel):
    """Like response model."""
    user: UserResponse
    created_at: datetime

class LivestreamResponse(LiveStream):
    """Enhanced livestream response model with additional metadata."""
    host: UserResponse
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False
    
    model_config = ConfigDict(from_attributes=True)  # For Pydantic v2

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Connection Manager for WebSockets ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, livestream_id: int, db: Session):
        await websocket.accept()
        if livestream_id not in self.active_connections:
            self.active_connections[livestream_id] = set()
        self.active_connections[livestream_id].add(websocket)
        await self.update_and_broadcast_viewer_count(livestream_id, db)

    async def disconnect(self, websocket: WebSocket, livestream_id: int, db: Session):
        if livestream_id in self.active_connections and websocket in self.active_connections[livestream_id]:
            self.active_connections[livestream_id].remove(websocket)
            await self.update_and_broadcast_viewer_count(livestream_id, db)

    async def broadcast(self, message: str, livestream_id: int):
        if livestream_id in self.active_connections:
            connections = self.active_connections[livestream_id]
            for connection in connections:
                await connection.send_text(message)

    async def update_and_broadcast_viewer_count(self, livestream_id: int, db: Session):
        count = 0
        if livestream_id in self.active_connections:
            count = len(self.active_connections[livestream_id])
        
        livestream = db.query(models.LiveStream).filter(models.LiveStream.id == livestream_id).first()
        if livestream:
            livestream.viewer_count = count
            db.commit()
        
        await self.broadcast(json.dumps({"type": "viewer_count", "count": count}), livestream_id)

manager = ConnectionManager()

# --- Helper Functions ---

def check_blocked_users(db: Session, user_id: int, target_id: int) -> bool:
    """Check if there's a block relationship between two users."""
    blocked = db.query(models.Block).filter(
        ((models.Block.blocker_id == user_id) & (models.Block.blocked_id == target_id)) |
        ((models.Block.blocker_id == target_id) & (models.Block.blocked_id == user_id))
    ).first()
    return blocked is not None

# --- API Endpoints ---

@router.post(
    "/start", 
    response_model=LivestreamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new livestream",
    description="""
    Start a new livestream session.
    
    - **user_id**: ID of the user starting the stream (required)
    - Returns the created livestream with initial stats
    
    Note: A user can only have one active livestream at a time.
    """,
    responses={
        201: {"description": "Livestream started successfully"},
        400: {"description": "User already has an active livestream"}
    }
)
async def start_livestream(
    user_id: int = Query(..., description="The ID of the user starting the stream"), 
    db: Session = Depends(get_db)
):
    """Starts a new livestream."""
    # Check if user already has an active livestream
    active_stream = db.query(models.LiveStream).filter(
        models.LiveStream.host_id == user_id,
        models.LiveStream.status == "active"
    ).first()
    
    if active_stream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active livestream"
        )
    
    new_livestream = models.LiveStream(host_id=user_id, status="active")
    db.add(new_livestream)
    db.commit()
    db.refresh(new_livestream)
    
    # Convert to Pydantic model to include computed fields
    return LiveStream(
        **new_livestream.__dict__,
        host={"id": user_id},  # Will be populated with user data in the response model
        like_count=0,
        comment_count=0,
        is_liked=False
    )

@router.post(
    "/{livestream_id}/end", 
    response_model=LivestreamResponse,
    summary="End a livestream",
    description="""
    End an active livestream.
    
    - **livestream_id**: ID of the livestream to end (required)
    - **save_as_post**: Whether to save the livestream as a post (default: false)
    - **user_id**: ID of the user ending the stream (must be the host)
    
    Returns the ended livestream with updated status and stats.
    """,
    responses={
        200: {"description": "Livestream ended successfully"},
        400: {"description": "Livestream has already ended"},
        403: {"description": "Not authorized to end this livestream"},
        404: {"description": "Livestream not found"}
    }
)
async def end_livestream(
    livestream_id: int,
    save_as_post: bool = Query(False, description="Set to true to save the livestream as a post."),
    user_id: int = Query(..., description="The ID of the user ending the stream"),
    db: Session = Depends(get_db)
):
    """Ends a livestream and optionally saves it as a post."""
    # Get livestream with host relationship loaded
    livestream = db.query(models.LiveStream).options(
        joinedload(models.LiveStream.host)
    ).filter(
        models.LiveStream.id == livestream_id, 
        models.LiveStream.host_id == user_id
    ).first()

    if not livestream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livestream not found or you are not the host.")
    if livestream.status == "ended":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Livestream has already ended.")

    livestream.status = "ended"
    livestream.end_time = datetime.utcnow()

    if save_as_post:
        new_post = models.Post(
            content=f"Check out the recording of my live stream from {livestream.start_time.strftime('%Y-%m-%d')}!",
            media_url=json.dumps({"type": "video", "url": f"/recordings/livestream_{livestream.id}.mp4"}), # Placeholder
            owner_id=user_id
        )
        db.add(new_post)
        db.flush()
        livestream.saved_post_id = new_post.id

    db.commit()
    db.refresh(livestream)
    
    # Create a dictionary without the host relationship to avoid conflicts
    livestream_dict = {k: v for k, v in livestream.__dict__.items() if k != '_sa_instance_state' and k != 'host'}
    
    # Convert to Pydantic model
    return LiveStream(
        **livestream_dict,
        host={
            "id": livestream.host.id,
            "username": livestream.host.username,
            "profile_picture": livestream.host.profile_picture or ""
        },
        like_count=len(livestream.likes) if hasattr(livestream, 'likes') else 0,
        comment_count=len(livestream.comments) if hasattr(livestream, 'comments') else 0,
        is_liked=False  # This would require checking against the current user
    )

class CommentResponse(LiveStreamComment):
    """Enhanced comment response model with additional metadata."""
    user: Dict[str, Any] = Field(..., description="User who posted the comment")
    is_owner: bool = Field(..., description="Whether the current user is the comment author")
    can_delete: bool = Field(..., description="Whether the current user can delete this comment")
    
    model_config = ConfigDict(from_attributes=True)  # This replaces the old `orm_mode = True` in Pydantic v2


@router.get(
    "/{livestream_id}/comments", 
    response_model=List[CommentResponse],
    summary="Get Livestream Comments",
    description="""
    Retrieves comments for a specific livestream with pagination.
    
    - **livestream_id**: ID of the livestream
    - **current_user_id**: ID of the current user for permission checks
    - **skip**: Number of comments to skip (for pagination)
    - **limit**: Maximum number of comments to return (max 100)
    
    Returns comments sorted by creation date (newest first)
    """,
    responses={
        200: {"description": "List of comments"},
        403: {"description": "Access denied - user is blocked"},
        404: {"description": "Livestream not found"}
    }
)
async def get_livestream_comments(
    livestream_id: int = PathParam(..., description="ID of the livestream to get comments for"),
    current_user_id: int = Query(..., description="Current user's ID for permission checks"),
    skip: int = Query(0, ge=0, description="Number of comments to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of comments to return"),
    db: Session = Depends(get_db)
):
    # Check if livestream exists and is active
    livestream = db.query(models.LiveStream).filter(
        models.LiveStream.id == livestream_id,
        models.LiveStream.status == 'active'
    ).first()
    
    if not livestream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Livestream not found or has ended"
        )
    
    # Check block status between users
    if check_blocked_users(db, current_user_id, livestream.host_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view comments on this livestream"
        )
    
    # Get comments with user info and eager loading
    comments_query = db.query(models.LiveStreamComment).options(
        joinedload(models.LiveStreamComment.user)
    ).filter(
        models.LiveStreamComment.livestream_id == livestream_id
    ).order_by(
        models.LiveStreamComment.created_at.desc()
    )
    
    total_comments = comments_query.count()
    comments = comments_query.offset(skip).limit(limit).all()
    
    # Build response with additional metadata
    result = []
    for comment in comments:
        if not hasattr(comment, 'user') or not comment.user:
            continue  # Skip comments without user data
            
        # Check permissions
        is_owner = comment.user_id == current_user_id
        can_delete = is_owner or current_user_id == livestream.host_id
        
        # Create response object
        result.append(CommentResponse(
            id=comment.id,
            text=comment.text,
            created_at=comment.created_at,
            user_id=comment.user_id,
            livestream_id=comment.livestream_id,
            user={
                'id': comment.user.id,
                'username': comment.user.username,
                'profile_picture': comment.user.profile_picture or ""
            },
            is_owner=is_owner,
            can_delete=can_delete
        ))
    
    # Add pagination headers
    response_headers = {
        'X-Total-Count': str(total_comments),
        'X-Page-Size': str(limit),
        'X-Page-Offset': str(skip)
    }
    
    response = [r.model_dump() for r in result]  # Use model_dump() instead of dict() in Pydantic v2
    return Response(
        content=json.dumps(response, default=str),
        media_type="application/json",
        headers=response_headers
    )

@router.post(
    "/{livestream_id}/comments", 
    response_model=CommentResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Post a comment on a livestream",
    description="""
    Add a comment to a livestream.
    
    - **livestream_id**: ID of the livestream to comment on (required)
    - **text**: The comment text (required)
    - **current_user_id**: ID of the user posting the comment (required)
    
    Returns the created comment with user info.
    """,
    responses={
        201: {"description": "Comment posted successfully"},
        403: {"description": "Not authorized to comment on this livestream"},
        404: {"description": "Livestream not found or has ended"}
    }
)
async def create_livestream_comment(
    livestream_id: int,
    comment: LiveStreamCommentCreate,
    current_user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    """Add a comment to a livestream."""
    # Check if user exists
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if livestream exists and is active
    livestream = db.query(models.LiveStream).filter(
        models.LiveStream.id == livestream_id,
        models.LiveStream.status == 'active'
    ).first()
    
    if not livestream:
        raise HTTPException(status_code=404, detail="Active livestream not found")
    
    # Check if current user is blocked by the host or vice versa
    if check_blocked_users(db, current_user_id, livestream.host_id):
        raise HTTPException(status_code=403, detail="You cannot comment on this livestream")
    
    # Create comment
    db_comment = models.LiveStreamComment(
        text=comment.text,
        user_id=current_user_id,
        livestream_id=livestream_id
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    # Broadcast new comment via WebSocket
    await manager.broadcast(json.dumps({
        "type": "new_comment",
        "comment": {
            "id": db_comment.id,
            "text": db_comment.text,
            "created_at": db_comment.created_at.isoformat(),
            "user": {
                "id": user.id,
                "username": user.username,
                "profile_picture": user.profile_picture or ""
            }
        }
    }), livestream_id)
    
    return LiveStreamComment(
        **db_comment.__dict__,
        user={
            'id': user.id,
            'username': user.username,
            'profile_picture': user.profile_picture or ""
        }
    )

@router.delete("/comments/{comment_id}", status_code=204)
async def delete_livestream_comment(
    comment_id: int,
    current_user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    """Delete a comment. Only the comment author or livestream host can delete."""
    comment = db.query(models.LiveStreamComment).options(
        joinedload(models.LiveStreamComment.livestream)
    ).filter(
        models.LiveStreamComment.id == comment_id
    ).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Check if current user is the comment author or livestream host
    if comment.user_id != current_user_id and comment.livestream.host_id != current_user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
    
    db.delete(comment)
    db.commit()
    return None

@router.post(
    "/{livestream_id}/like", 
    status_code=status.HTTP_200_OK,
    summary="Like or unlike a livestream",
    description="""
    Toggle like on a livestream.
    
    - **livestream_id**: ID of the livestream to like/unlike (required)
    - **current_user_id**: ID of the user liking/unliking (required)
    
    Returns the current like status and total like count.
    """,
    responses={
        200: {"description": "Like status toggled successfully"},
        403: {"description": "Not authorized to like this livestream"},
        404: {"description": "Livestream not found or has ended"}
    }
)
async def like_livestream(
    livestream_id: int,
    current_user_id: int = Query(..., description="Current user's ID"),
    db: Session = Depends(get_db)
):
    """Like or unlike a livestream."""
    # Check if user exists
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if livestream exists and is active
    livestream = db.query(models.LiveStream).filter(
        models.LiveStream.id == livestream_id,
        models.LiveStream.status == 'active'
    ).first()
    
    if not livestream:
        raise HTTPException(status_code=404, detail="Active livestream not found")
    
    # Check if current user is blocked by the host or vice versa
    if check_blocked_users(db, current_user_id, livestream.host_id):
        raise HTTPException(status_code=403, detail="You cannot like this livestream")
    
    # Check if already liked
    like = db.query(models.LiveStreamLike).filter(
        models.LiveStreamLike.user_id == current_user_id,
        models.LiveStreamLike.livestream_id == livestream_id
    ).first()
    
    if like:
        # Unlike
        db.delete(like)
        is_liked = False
    else:
        # Like
        like = models.LiveStreamLike(
            user_id=current_user_id,
            livestream_id=livestream_id
        )
        db.add(like)
        is_liked = True
    
    db.commit()
    
    # Get updated like count
    like_count = db.query(models.LiveStreamLike).filter(
        models.LiveStreamLike.livestream_id == livestream_id
    ).count()
    
    # Broadcast like update via WebSocket
    if is_liked:
        await manager.broadcast(json.dumps({
            "type": "new_like",
            "user": {
                "id": user.id,
                "username": user.username,
                "profile_picture": user.profile_picture or ""
            },
            "like_count": like_count
        }), livestream_id)
    
    return {"is_liked": is_liked, "like_count": like_count}

@router.get("/{livestream_id}/likes", response_model=List[Dict[str, Any]])
async def get_livestream_likes(
    livestream_id: int,
    current_user_id: int = Query(..., description="Current user's ID"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get users who liked a livestream."""
    # Check if livestream exists
    livestream = db.query(models.LiveStream).filter(
        models.LiveStream.id == livestream_id
    ).first()
    
    if not livestream:
        raise HTTPException(status_code=404, detail="Livestream not found")
    
    # Check if current user is blocked by the host or vice versa
    if check_blocked_users(db, current_user_id, livestream.host_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get likes with user info
    likes = db.query(models.LiveStreamLike).options(
        joinedload(models.LiveStreamLike.user)
    ).filter(
        models.LiveStreamLike.livestream_id == livestream_id
    ).order_by(
        models.LiveStreamLike.id.desc()
    ).offset(skip).limit(limit).all()
    
    return [
        {
            'id': like.user.id,
            'username': like.user.username,
            'profile_picture': like.user.profile_picture,
            'liked_at': like.created_at.isoformat() if hasattr(like, 'created_at') else None
        }
        for like in likes
    ]

@router.websocket("/{livestream_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    livestream_id: int, 
    user_id: int = Query(...), 
    db: Session = Depends(get_db)
):
    await manager.connect(websocket, livestream_id, db)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type")

                if message_type == "comment":
                    text = message_data.get("text")
                    if text:
                        # Get user info for the comment
                        user = db.query(models.User).get(user_id)
                        if not user:
                            continue
                            
                        comment = models.LiveStreamComment(
                            text=text, 
                            user_id=user_id, 
                            livestream_id=livestream_id
                        )
                        db.add(comment)
                        db.commit()
                        db.refresh(comment)
                        
                        # Create comment response with user info
                        comment_data = {
                            "id": comment.id,
                            "text": comment.text,
                            "created_at": comment.created_at.isoformat(),
                            "user": {
                                "id": user.id,
                                "username": user.username,
                                "profile_picture": user.profile_picture
                            }
                        }
                        
                        await manager.broadcast(json.dumps({
                            "type": "new_comment",
                            "comment": comment_data
                        }), livestream_id)

                elif message_type == "like":
                    existing_like = db.query(models.LiveStreamLike).filter_by(user_id=user_id, livestream_id=livestream_id).first()
                    if not existing_like:
                        # Get user info for the like
                        user = db.query(models.User).get(user_id)
                        if not user:
                            continue
                            
                        like = models.LiveStreamLike(
                            user_id=user_id, 
                            livestream_id=livestream_id
                        )
                        db.add(like)
                        db.commit()
                        
                        # Create like response with user info
                        await manager.broadcast(json.dumps({
                            "type": "new_like", 
                            "user": {
                                "id": user.id,
                                "username": user.username,
                                "profile_picture": user.profile_picture
                            }
                        }), livestream_id)
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket, livestream_id, db)
