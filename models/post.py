from datetime import datetime, timezone, timedelta
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Table, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from typing import Optional, TYPE_CHECKING, List

from database import Base

# Import for type checking to avoid circular imports
if TYPE_CHECKING:
    from models.user import User
    from models.comment import Comment
    from models.blocked_post import BlockedPost

# Many-to-many relationship for post likes
post_likes = Table(
    'post_likes',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('post_id', Integer, ForeignKey('posts.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime(timezone=True), server_default=func.now(), nullable=False)
)

# Define media types as a proper SQLAlchemy enum
class MediaType(str, PyEnum):
    IMAGE = "image"
    VIDEO = "video"

# Create a SQLAlchemy enum type
media_type_enum = PgEnum(
    MediaType, 
    name='media_type_enum',
    create_constraint=True,
    validate_strings=True
)

class Post(Base):
    """Post model for storing user posts with media and metadata."""
    
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=True, comment='Text content of the post')
    media_url = Column(String(512), nullable=True, comment='URL to the media file')
    media_type = Column(media_type_enum, nullable=True, comment='Type of media (image or video)')
    created_ip = Column(String(45), nullable=True, comment='IP address of the user who created the post')
    country_code = Column(String(2), nullable=True, comment='Country code of the post creator')
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    @property
    def validate_media_fields(self) -> 'PostCreate':
        """Validate media fields."""
        if self.media_url and not self.media_type:
            raise ValueError("media_type is required when media_url is provided")
        if self.media_type and not self.media_url:
            raise ValueError("media_url is required when media_type is provided")
        if self.media_url and self.media_type:
            if self.media_type not in [MediaType.IMAGE, MediaType.VIDEO]:
                raise ValueError(f"Invalid media_type: {self.media_type}")
            if not self.media_url.startswith('/media/posts/'):
                raise ValueError("media_url must start with '/media/posts/'")
        return self

    @property
    def has_media(self) -> bool:
        """Check if the post has media."""
        return bool(self.media_url and self.media_type)
    
    @property
    def media_info(self) -> Optional[dict]:
        """Get media information as a dictionary."""
        if self.has_media:
            return {
                'url': self.media_url,
                'type': self.media_type,
                'created_at': self.created_at.isoformat()
            }
        return None
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # User reference
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    owner = relationship(
        'User',
        back_populates='posts',
        doc="User who created this post"
    )
    
    # Location fields
    latitude = Column(Float, nullable=True, comment='Latitude coordinate of the post location')
    longitude = Column(Float, nullable=True, comment='Longitude coordinate of the post location')
    location_name = Column(String(255), nullable=True, comment='Human-readable location name')
    
    # Media enhancement fields
    filter_type = Column(String(50), nullable=True, comment='Filter applied to the media')
    text_overlay = Column(Text, nullable=True, comment='Text overlay on the media')
    text_position = Column(String(20), nullable=True, comment='Position of the text overlay')
    sticker_id = Column(Integer, nullable=True, comment='ID of the sticker applied to the media')
    
    # Security and metadata
    is_encrypted = Column(Boolean, default=False, nullable=False, server_default='false', 
                         comment='Whether the post content is encrypted')
    is_archived = Column(Boolean, default=False, nullable=False, server_default='false',
                        comment='Whether the post is archived (soft delete)')
    
    # Relationships - using string-based references to avoid circular imports
    liked_by = relationship(
        'User',
        secondary=post_likes,
        back_populates='liked_posts',
        doc="Users who liked this post"
    )
    
    # Relationship with Like model
    likes = relationship(
        'Like',
        back_populates='post',
        cascade='all, delete-orphan',
        doc="Like instances for this post"
    )
    
    # Relationship with PostSave model
    saves = relationship(
        'PostSave',
        back_populates='post',
        cascade='all, delete-orphan',
        doc="Post save instances for this post"
    )
    
    # Relationship with PostView model
    views = relationship(
        'PostView',
        back_populates='post',
        cascade='all, delete-orphan',
        doc="View instances for this post"
    )
    
    comments = relationship(
        'Comment',
        back_populates='post',
        cascade='all, delete-orphan',
        doc="Comments on this post"
    )
    
    blocked_by_users = relationship(
        'BlockedPost',
        back_populates='post',
        cascade='all, delete-orphan',
        doc="Users who have blocked this post"
    )
    
    def to_dict(self, include_user: bool = True) -> dict:
        """Convert the post to a dictionary."""
        data = {
            'id': self.id,
            'content': self.content,
            'media_url': self.media_url,
            'media_type': self.media_type.value if self.media_type else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_id': self.user_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'location_name': self.location_name,
            'filter_type': self.filter_type,
            'text_overlay': self.text_overlay,
            'text_position': self.text_position,
            'sticker_id': self.sticker_id,
            'is_encrypted': self.is_encrypted,
            'like_count': len(self.likes) if hasattr(self, 'likes') else 0,
            'comment_count': len(self.comments) if hasattr(self, 'comments') else 0,
            'is_liked': False,  # Will be set by the service layer if needed
            'is_saved': False,  # Will be set by the service layer if needed
        }
        
        if include_user:
            # Check if owner exists and is not None
            if self.owner:
                data['user'] = {
                    'id': self.owner.id,
                    'username': self.owner.username,
                    'avatar_url': getattr(self.owner, 'avatar_url', None),
                    'is_verified': getattr(self.owner, 'is_verified', False)
                }
            else:
                # If owner is None, provide default values
                data['user'] = {
                    'id': None,
                    'username': 'deleted_user',
                    'avatar_url': None,
                    'is_verified': False
                }          
        return data
        
    def __repr__(self) -> str:
        return f"<Post {self.id} by User {self.user_id}>"
