import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Boolean, String, Enum
from sqlalchemy.orm import relationship
from database import Base

class MessageType(str, PyEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"
    AUDIO = "audio"
    DOCUMENT = "document"

# Create a SQLAlchemy-compatible enum
MessageTypeEnum = Enum(
    *[e.value for e in MessageType],
    name="message_type_enum"
)

class MessageAttachment(Base):
    __tablename__ = 'message_attachments'
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey('messages.id'))
    channel_message_id = Column(Integer, ForeignKey('channel_messages.id'))
    file_url = Column(String, nullable=False)
    file_type = Column(MessageTypeEnum, nullable=False)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer)  # Size in bytes
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    message = relationship("Message", back_populates="attachments")
    channel_message = relationship("ChannelMessage", back_populates="attachments")


class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=True)  # Can be null if only file is sent
    message_type = Column(MessageTypeEnum, default=MessageType.TEXT.value)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    from_user_id = Column(Integer, ForeignKey('users.id'))
    to_user_id = Column(Integer, ForeignKey('users.id'))
    is_read = Column(Boolean, default=False, nullable=False)
    deleted_for_sender = Column(Boolean, default=False)
    deleted_for_recipient = Column(Boolean, default=False)

    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="messages_sent")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="messages_received")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")
