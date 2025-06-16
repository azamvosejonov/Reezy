from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from typing import TYPE_CHECKING

from database import Base

# Import for type checking to avoid circular imports
if TYPE_CHECKING:
    from .user import User
    from .post import Post

class Like(Base):
    __tablename__ = 'likes'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)

    # Relationships - using string-based references to avoid circular imports
    owner = relationship(
        "User",
        back_populates="likes",
        overlaps="liked_posts"
    )
    
    post = relationship(
        "Post",
        back_populates="likes",
        overlaps="liked_by"
    )

    __table_args__ = (UniqueConstraint('owner_id', 'post_id', name='_user_post_like_uc'),)
