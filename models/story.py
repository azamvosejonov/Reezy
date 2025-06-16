import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class Story(Base):
    __tablename__ = 'stories'
    id = Column(Integer, primary_key=True, index=True)
    media_url = Column(String, nullable=True)  # Made nullable to allow stories without media
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.datetime.utcnow() + datetime.timedelta(hours=24))
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    owner = relationship("User", back_populates="stories")
    views = relationship("StoryView", back_populates="story", cascade="all, delete-orphan")
    likes = relationship("StoryLike", back_populates="story", cascade="all, delete-orphan")
    comments = relationship("StoryComment", back_populates="story", cascade="all, delete-orphan")

class StoryView(Base):
    __tablename__ = 'story_views'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    story_id = Column(Integer, ForeignKey('stories.id'), nullable=False)
    viewed_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="story_views")
    story = relationship("Story", back_populates="views")

class StoryLike(Base):
    __tablename__ = 'story_likes'
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    story_id = Column(Integer, ForeignKey('stories.id'), nullable=False)

    owner = relationship("User", back_populates="story_likes")
    story = relationship("Story", back_populates="likes")

class StoryComment(Base):
    __tablename__ = 'story_comments'
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    story_id = Column(Integer, ForeignKey('stories.id'), nullable=False)

    owner = relationship("User", back_populates="story_comments")
    story = relationship("Story", back_populates="comments")
