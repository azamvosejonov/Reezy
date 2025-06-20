from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from database import get_db
from models.post import Post, post_likes
from models.user import User
from routers.auth import get_current_user
from schemas.post import PostResponse

router = APIRouter()

@router.post(
    "/posts/{post_id}/like",
    summary="Postga like bosish",
    description="Postga like bosish yoki like o'chirish",
    tags=["Post Actions"]
)
async def like_post(
    post_id: int = Path(..., description="Post ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Postga like bosish endpointi"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")
    
    # Like mavjudligini tekshirish
    like = db.query(post_likes).filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if like:
        # Agar like mavjud bo'lsa uni o'chirish
        db.query(post_likes).filter_by(user_id=current_user.id, post_id=post_id).delete()
        db.commit()
        return {"message": "Like o'chirildi", "liked": False}
    else:
        # Agar like mavjud bo'lmasa yangi like qo'shish
        db.execute(post_likes.insert().values(user_id=current_user.id, post_id=post_id))
        db.commit()
        return {"message": "Like qo'shildi", "liked": True}

@router.get(
    "/posts/{post_id}/likes",
    response_model=List[PostResponse],
    summary="Post like bosganlarini ko'rish",
    description="Postga like bosgan foydalanuvchilar ro'yxatini olish",
    tags=["Post Actions"]
)
async def get_post_likes(
    post_id: int = Path(..., description="Post ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Postga like bosgan foydalanuvchilar ro'yxatini olish"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")
    
    # Like bosgan foydalanuvchilar
    likes = db.query(post_likes).filter_by(post_id=post_id).all()
    
    # Foydalanuvchilar ro'yxatini tayyorlash
    users = []
    for like in likes:
        user = db.query(User).filter(User.id == like.user_id).first()
        if user:
            users.append({
                "id": user.id,
                "username": user.username,
                "profile_picture": user.profile_picture
            })
    
    return users

@router.post(
    "/posts/{post_id}/save",
    summary="Postni saqlash",
    description="Postni saqlash yoki saqlangan postni o'chirish",
    tags=["Post Actions"]
)
async def save_post(
    post_id: int = Path(..., description="Post ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Postni saqlash endpointi"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")
    
    # Postni saqlash
    saved_post = db.query(Post).filter(
        Post.id == post_id,
        Post.user_id == current_user.id
    ).first()
    
    if saved_post:
        # Agar post saqlangan bo'lsa uni o'chirish
        db.delete(saved_post)
        db.commit()
        return {"message": "Post saqlanmadi", "saved": False}
    else:
        # Agar post saqlanmagan bo'lsa saqlash
        saved_post = Post(
            content=post.content,
            media_url=post.media_url,
            media_type=post.media_type,
            user_id=current_user.id,
            created_at=datetime.now()
        )
        db.add(saved_post)
        db.commit()
        return {"message": "Post saqlandi", "saved": True}

@router.get(
    "/posts/{post_id}/comments",
    response_model=List[PostResponse],
    summary="Post commentlarini ko'rish",
    description="Post commentlarini olish",
    tags=["Post Actions"]
)
async def get_post_comments(
    post_id: int = Path(..., description="Post ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Post commentlarini olish endpointi"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")
    
    # Post commentlarini olish
    comments = db.query(Post).filter(Post.parent_id == post_id).all()
    
    # Commentlar ro'yxatini tayyorlash
    comment_list = []
    for comment in comments:
        comment_list.append({
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at,
            "user": {
                "id": comment.user_id,
                "username": comment.user.username,
                "profile_picture": comment.user.profile_picture
            }
        })
    
    return comment_list
