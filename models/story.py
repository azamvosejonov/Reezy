import datetime
from datetime import timedelta
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

# Media type will be determined from file extension
# We'll use a helper function to determine media type from URL
def get_media_type_from_url(url):
    if not url:
        return None
    url_lower = url.lower()
    if any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
        return 'image'
    elif any(ext in url_lower for ext in ['.mp4', '.webm', '.mov', '.avi']):
        return 'video'
    return None

class Story(Base):
    """Story model for temporary user stories that expire after a set time."""
    __tablename__ = 'stories'
    __table_args__ = {'comment': 'Stores temporary user stories that expire after 24 hours by default'}
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column('owner_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Media fields
    media_url = Column(String(512), nullable=False, comment='URL to the story media file')
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Relationships
    user = relationship('User', foreign_keys=[owner_id], back_populates='stories')
    views = relationship('StoryView', back_populates='story', cascade='all, delete-orphan', lazy='dynamic')
    likes = relationship("StoryLike", back_populates="story", cascade="all, delete-orphan", lazy='dynamic')
    comments = relationship("StoryComment", back_populates="story", cascade="all, delete-orphan", lazy='dynamic')
    
    def __init__(self, **kwargs):
        # Handle user_id -> owner_id mapping for backward compatibility
        if 'user_id' in kwargs and 'owner_id' not in kwargs:
            kwargs['owner_id'] = kwargs.pop('user_id')
            
        # Set default expiration to 24 hours from creation if not specified
        if 'expires_at' not in kwargs and 'expires_in_hours' not in kwargs:
            kwargs['expires_at'] = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        elif 'expires_in_hours' in kwargs:
            expires_in_hours = kwargs.pop('expires_in_hours')
            kwargs['expires_at'] = datetime.datetime.utcnow() + datetime.timedelta(hours=expires_in_hours)
        super().__init__(**kwargs)
    
    @property
    def view_count(self) -> int:
        """Return the number of views for this story."""
        return self.views.count()
    
    @property
    def like_count(self) -> int:
        """Return the number of likes for this story."""
        return self.likes.count()
    
    @property
    def comment_count(self) -> int:
        """Return the number of comments for this story."""
        return self.comments.count()
    
    @property
    def is_expired(self) -> bool:
        """Check if the story has expired."""
        return datetime.datetime.utcnow() > self.expires_at
    
    @property
    def media_type(self):
        """Get media type from file extension."""
        return get_media_type_from_url(self.media_url)
        
    @property
    def media_type_str(self):
        """Alias for media_type for backward compatibility."""
        return self.media_type
    
    def to_dict(self) -> dict:
        """Convert the story to a dictionary."""
        is_expired = self.is_expired
        return {
            'id': self.id,
            'user_id': self.owner_id,  # For backward compatibility
            'owner_id': self.owner_id,
            'media_url': self.media_url,
            'media_type': self.media_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': not is_expired,  # Calculate based on expiration
            'view_count': self.view_count,
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'is_expired': is_expired,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'avatar_url': getattr(self.user, 'avatar_url', None),
                'is_verified': getattr(self.user, 'is_verified', False)
            } if hasattr(self, 'user') and self.user else None
        }
    
    def __repr__(self) -> str:
        return f"<Story {self.id} by User {self.user_id}>"

class StoryView(Base):
    """Tracks which users have viewed which stories."""
    __tablename__ = 'story_views'
    __table_args__ = {'comment': 'Tracks which users have viewed which stories'}
    
    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_id = Column('owner_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    viewed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    story = relationship('Story', back_populates='views')
    user = relationship('User', foreign_keys=[owner_id], back_populates='story_views')
    
    def to_dict(self) -> dict:
        """Convert the story view to a dictionary."""
        return {
            'id': self.id,
            'story_id': self.story_id,
            'user_id': self.owner_id,  # For backward compatibility
            'owner_id': self.owner_id,
            'viewed_at': self.viewed_at.isoformat() if self.viewed_at else None,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'avatar_url': getattr(self.user, 'avatar_url', None)
            } if hasattr(self, 'user') and self.user else None
        }
    
    def __repr__(self) -> str:
        return f"<StoryView {self.id} for Story {self.story_id} by User {self.owner_id}>"


class StoryLike(Base):
    """Tracks which users have liked which stories."""
    __tablename__ = 'story_likes'
    __table_args__ = (
        {'comment': 'Tracks which users have liked which stories'}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column('owner_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    story_id = Column(Integer, ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Relationships
    user = relationship('User', foreign_keys=[owner_id], back_populates='story_likes')
    story = relationship('Story', back_populates='likes')
    
    def __init__(self, **kwargs):
        # Remove created_at if it's passed in kwargs since we don't have that column
        kwargs.pop('created_at', None)
        super().__init__(**kwargs)
    
    def to_dict(self) -> dict:
        """Convert the story like to a dictionary."""
        return {
            'id': self.id,
            'story_id': self.story_id,
            'user_id': self.owner_id,  # For backward compatibility
            'owner_id': self.owner_id,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'avatar_url': getattr(self.user, 'avatar_url', None)
            } if hasattr(self, 'user') and self.user else None
        }
    
    def __repr__(self) -> str:
        return f"<StoryLike {self.id} for Story {self.story_id} by User {self.owner_id}>"


class StoryComment(Base):
    """Comments on stories."""
    __tablename__ = 'story_comments'
    __table_args__ = (
        {'comment': 'Comments on stories'}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    owner_id = Column('owner_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    story_id = Column(Integer, ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Relationships
    user = relationship('User', foreign_keys=[owner_id], back_populates='story_comments')
    story = relationship('Story', back_populates='comments')
    
    def __init__(self, **kwargs):
        # Ensure created_at is set to now if not provided
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.datetime.utcnow()
        super().__init__(**kwargs)
    
    def to_dict(self) -> dict:
        """Convert the story comment to a dictionary."""
        return {
            'id': self.id,
            'text': self.text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_id': self.owner_id,  # For backward compatibility
            'owner_id': self.owner_id,
            'story_id': self.story_id,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'avatar_url': getattr(self.user, 'avatar_url', None)
            } if hasattr(self, 'user') and self.user else None
        }
    
    def __repr__(self) -> str:
        return f"<StoryComment {self.id} by User {self.owner_id} on Story {self.story_id}>"
