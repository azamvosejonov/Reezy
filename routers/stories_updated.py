from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, Request, Query, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any
import os
import uuid
from datetime import datetime, timedelta
import json

import app.models as models
from database import SessionLocal
from routers.stories import StoriesResponse

router = APIRouter()
# ... (other imports and code)

def get_db():
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        print(f"Database error: {e}")
        raise
    finally:
        db.close()


@router.get("", 
    response_model=StoriesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stories",
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
            story_data = {
                "id": story.id,
                "user_id": story.owner_id,
                "user_name": story.owner.username if story.owner else "Unknown",
                "user_avatar": story.owner.avatar if story.owner and hasattr(story.owner, 'avatar') else None,
                "text": story.text,
                "image": story.image,
                "video": story.video,
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
