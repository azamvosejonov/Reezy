from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, ForeignKey, DateTime, func, String, Text
from sqlalchemy.orm import relationship

from database import Base

class BlockedPost(Base):
    """
    Model representing a post that has been blocked by a user.
    
    When a user blocks a post, it will no longer be visible to them in their feed
    or search results. This is different from content moderation where a post might
    be removed for all users.
    """
    __tablename__ = 'blocked_posts'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, 
                    doc="ID of the user who blocked the post")
    post_id = Column(Integer, ForeignKey('posts.id', ondelete='CASCADE'), nullable=False,
                    doc="ID of the post that was blocked")
    reason = Column(String(255), nullable=True, 
                   doc="Optional reason for blocking the post")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False,
                      doc="Timestamp when the post was blocked")
    
    # Relationships - using string-based references to avoid circular imports
    user = relationship(
        "User",
        back_populates="blocked_posts",
        doc="User who blocked the post"
    )
    
    post = relationship(
        "Post",
        back_populates="blocked_by_users",
        doc="Post that was blocked"
    )
