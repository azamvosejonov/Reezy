from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from pydantic import BaseModel
from datetime import datetime

from models import User, Follower
from database import SessionLocal
from schemas.user import UserResponse

# Pydantic model for the follow request body
class FollowRequest(BaseModel):
    followed_id: int

router = APIRouter(prefix="/api/relationships", tags=["relationships"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# WARNING: Authentication is temporarily disabled for testing.
# A hardcoded user ID (1) is used instead of an authenticated user.

@router.post("/follow", status_code=status.HTTP_201_CREATED)
async def follow_user(
    follow_request: FollowRequest,
    db: Session = Depends(get_db)
):
    follower_id = 1  # Hardcoded user ID for testing
    followed_id = follow_request.followed_id

    if follower_id == followed_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself"
        )

    existing_follow = db.query(Follower).filter(
        Follower.follower_id == follower_id,
        Follower.followed_id == followed_id
    ).first()

    if existing_follow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already following this user"
        )

    followed_user = db.query(User).filter(User.id == followed_id).first()
    if not followed_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User to be followed not found"
        )

    new_follow = Follower(
        follower_id=follower_id,
        followed_id=followed_id,
        created_at=datetime.utcnow()
    )
    db.add(new_follow)
    db.commit()

    return {"message": f"Successfully followed user {followed_id}"}

@router.delete("/unfollow/{followed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    followed_id: int,
    db: Session = Depends(get_db)
):
    follower_id = 1  # Hardcoded user ID for testing

    follow_to_delete = db.query(Follower).filter(
        Follower.follower_id == follower_id,
        Follower.followed_id == followed_id
    ).first()

    if not follow_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not following this user"
        )

    db.delete(follow_to_delete)
    db.commit()
    return

from fastapi import Query

@router.get("/followers", response_model=List[UserResponse])
async def get_followers(
    user_id: int = Query(...), # user_id is now a query parameter
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    followers = (
        db.query(User)
        .join(Follower, Follower.follower_id == User.id)
        .filter(Follower.followed_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return followers

@router.get("/following", response_model=List[UserResponse])
async def get_following(
    user_id: int = Query(...), # user_id is now a query parameter
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    following = (
        db.query(User)
        .join(Follower, Follower.followed_id == User.id)
        .filter(Follower.follower_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return following
