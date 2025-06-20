import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    creator_id = Column(Integer, ForeignKey('users.id'))
    image = Column(String, nullable=True)  # Path to the group image
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    creator = relationship("User")
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = relationship("GroupMessage", back_populates="group", cascade="all, delete-orphan")

class GroupMember(Base):
    __tablename__ = 'group_members'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    group_id = Column(Integer, ForeignKey('groups.id'))
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="group_memberships")
    group = relationship("Group", back_populates="members")

class GroupMessage(Base):
    __tablename__ = 'group_messages'
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default='text', nullable=False)  # text, image, video, file, etc.
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey('users.id'))
    group_id = Column(Integer, ForeignKey('groups.id'))

    user = relationship("User")
    group = relationship("Group", back_populates="messages")
    attachments = relationship("GroupMessageAttachment", back_populates="message", cascade="all, delete-orphan")

class GroupMessageAttachment(Base):
    __tablename__ = 'group_message_attachments'
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey('group_messages.id', ondelete='CASCADE'))
    file_url = Column(String, nullable=False)
    file_type = Column(String(50), nullable=False)  # image, video, document, etc.
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    message = relationship("GroupMessage", back_populates="attachments")

class GroupAdmin(Base):
    __tablename__ = 'group_admins'
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey('groups.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    granted_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")
