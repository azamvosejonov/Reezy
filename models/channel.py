import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum
from sqlalchemy.orm import relationship
from database import Base
from .message import MessageType, MessageTypeEnum

class Channel(Base):
    __tablename__ = 'channels'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    image = Column(String, nullable=True)  # Path to the channel image
    creator_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)

    creator = relationship("User", back_populates="created_channels")
    subscribers = relationship("ChannelSubscriber", back_populates="channel", cascade="all, delete-orphan")
    messages = relationship("ChannelMessage", back_populates="channel", cascade="all, delete-orphan")

class ChannelSubscriber(Base):
    __tablename__ = 'channel_subscribers'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    channel_id = Column(Integer, ForeignKey('channels.id'))
    subscribed_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="channel_subscriptions")
    channel = relationship("Channel", back_populates="subscribers")

class ChannelMessage(Base):
    __tablename__ = 'channel_messages'
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=True)  # Can be null if only file is sent
    message_type = Column(MessageTypeEnum, default=MessageType.TEXT.value, nullable=False)
    from_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    channel_id = Column(Integer, ForeignKey('channels.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    channel = relationship("Channel", back_populates="messages")
    user = relationship("User")
    comments = relationship("ChannelComment", back_populates="message", cascade="all, delete-orphan")
    attachments = relationship("MessageAttachment", back_populates="channel_message", cascade="all, delete-orphan")


class ChannelComment(Base):
    __tablename__ = 'channel_comments'
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey('channel_messages.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    message = relationship("ChannelMessage", back_populates="comments")
    user = relationship("User")
