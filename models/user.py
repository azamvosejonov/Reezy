from datetime import datetime, timedelta
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, Table, func
from sqlalchemy.orm import relationship, backref
from passlib.context import CryptContext

from config import settings
from database import Base
from .sticker import UserCoin

# Import call models for type checking
if TYPE_CHECKING:
    from calls.models.call import Call, CallParticipant

# Import for type checking to avoid circular imports
if TYPE_CHECKING:
    from .follower import Follower
    from .block import Block
    from .advertisement import Advertisement
    from .post import Post
    from .comment import Comment
    from .blocked_post import BlockedPost
    from .post import Post
    from .like import Like
    from .post_save import PostSave
    from .post_view import PostView
    from .story import Story, StoryView, StoryLike, StoryComment
    from .reel import Reel, ReelLike, ReelComment
    from .message import Message
    from .group import Group, GroupMember, GroupMessage, GroupAdmin
    from .channel import Channel, ChannelSubscriber, ChannelMessage, ChannelComment
    from .notification import Notification
    from .password_reset_token import PasswordResetToken
    from .livestream import LiveStream, LiveStreamLike, LiveStreamComment
    from .follow_request import FollowRequest
    from .social_account import SocialAccount
    from .blocked_post import BlockedPost

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    """User model for storing user details."""
    __tablename__ = 'users'  # Base table name without prefix
    __table_args__ = {'schema': settings.SQLALCHEMY_DB_TABLE_PREFIX.rstrip('_') if settings.SQLALCHEMY_DB_TABLE_PREFIX else None}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    profile_picture = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    website = Column(String(255), nullable=True)
    is_private = Column(Boolean, default=False, nullable=False)
    app_lock_password = Column(String, nullable=True) # Hashed secondary password
    current_token = Column(String(512), index=True, nullable=True) # Current active JWT token

    # Location fields
    registration_ip = Column(String(45), nullable=True)  # IPv6 can be up to 45 chars
    last_ip = Column(String(45), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    timezone = Column(String(50), nullable=True)

    # Relationships - using string-based references to avoid circular imports
    posts = relationship(
        "Post", 
        back_populates="owner", 
        cascade="all, delete-orphan"
    )
    
    # Many-to-many relationship for liked posts (through post_likes table)
    liked_posts = relationship(
        "Post",
        secondary="post_likes",
        back_populates="liked_by",
        overlaps="likes"
    )
    
    # One-to-many relationship with Like model
    likes = relationship(
        "Like",
        back_populates="owner",
        cascade="all, delete-orphan",
        overlaps="liked_posts"
    )
    
    # One-to-many relationship with PostSave model
    saves = relationship(
        "PostSave",
        back_populates="owner",
        cascade="all, delete-orphan",
        doc="Posts saved by this user"
    )
    
    # One-to-many relationship for blocked posts
    blocked_posts = relationship(
        "BlockedPost",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    comments = relationship("Comment", back_populates="owner", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="owner", cascade="all, delete-orphan")
    saves = relationship("PostSave", back_populates="owner", cascade="all, delete-orphan")
    views = relationship("PostView", back_populates="owner", cascade="all, delete-orphan")
    
    # Follower relationships
    follower_relationships = relationship(
        "Follower",
        foreign_keys="[Follower.followed_id]",
        back_populates="followed",
        cascade="all, delete-orphan"
    )
    followed_relationships = relationship(
        "Follower",
        foreign_keys="[Follower.follower_id]",
        back_populates="follower",
        cascade="all, delete-orphan"
    )
    
    # Block relationships
    blocks_made = relationship(
        "Block", 
        foreign_keys="[Block.blocker_id]",
        back_populates="blocker",
        cascade="all, delete-orphan"
    )
    blocks_received = relationship(
        "Block",
        foreign_keys="[Block.blocked_id]",
        back_populates="blocked",
        cascade="all, delete-orphan"
    )

    # Story and Reel relationships
    stories = relationship("Story", back_populates="owner", cascade="all, delete-orphan")
    story_views = relationship("StoryView", back_populates="owner", cascade="all, delete-orphan")
    story_likes = relationship("StoryLike", back_populates="owner", cascade="all, delete-orphan")
    story_comments = relationship("StoryComment", back_populates="owner", cascade="all, delete-orphan")
    reels = relationship("Reel", back_populates="owner", cascade="all, delete-orphan")
    reel_likes = relationship("ReelLike", back_populates="owner", cascade="all, delete-orphan")
    reel_comments = relationship("ReelComment", back_populates="owner", cascade="all, delete-orphan")

    # Messaging
    messages_sent = relationship("Message", foreign_keys='Message.from_user_id', back_populates="from_user", cascade="all, delete-orphan")
    messages_received = relationship("Message", foreign_keys='Message.to_user_id', back_populates="to_user", cascade="all, delete-orphan")

    # Groups and Channels
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    created_channels = relationship("Channel", back_populates="creator", cascade="all, delete-orphan")
    channel_subscriptions = relationship("ChannelSubscriber", back_populates="user", cascade="all, delete-orphan")

    # LiveStream relationship
    livestreams = relationship("LiveStream", back_populates="host", cascade="all, delete-orphan")

    # Follow request relationships
    sent_follow_requests = relationship("FollowRequest", foreign_keys="FollowRequest.requester_id", back_populates="requester", cascade="all, delete-orphan")
    received_follow_requests = relationship("FollowRequest", foreign_keys="FollowRequest.requested_id", back_populates="requested", cascade="all, delete-orphan")

    # Notifications
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    # Password Reset Tokens
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    # Follower/Following relationships
    followers = relationship("Follower", foreign_keys="[Follower.following_id]", back_populates="following")
    following = relationship("Follower", foreign_keys="[Follower.follower_id]", back_populates="follower")

    # Social accounts (OAuth)
    social_accounts = relationship(
        "SocialAccount",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Call relationships - simplified string literals
    calls_made = relationship(
        "Call",
        foreign_keys="Call.caller_id",
        primaryjoin="User.id == Call.caller_id",
        viewonly=True,
        overlaps="initiated_calls"
    )
    
    calls_received = relationship(
        "Call",
        foreign_keys="Call.receiver_id",
        primaryjoin="User.id == Call.receiver_id",
        viewonly=True,
        overlaps="received_calls"
    )
    
    # Alias relationships with overlaps to avoid SQLAlchemy warnings
    initiated_calls = relationship(
        "Call",
        foreign_keys="Call.caller_id",
        primaryjoin="User.id == Call.caller_id",
        viewonly=True,
        overlaps="calls_made"
    )
    
    received_calls = relationship(
        "Call",
        foreign_keys="Call.receiver_id",
        primaryjoin="User.id == Call.receiver_id",
        viewonly=True,
        overlaps="calls_received"
    )
    
    # Call participations
    call_participations = relationship(
        "CallParticipant",
        foreign_keys="CallParticipant.user_id",
        primaryjoin="User.id == CallParticipant.user_id",
        viewonly=True
    )

    # Stickers and Coins
    stickers = relationship("UserSticker", back_populates="user", cascade="all, delete-orphan")
    coin_balance = relationship("UserCoin", uselist=False, back_populates="user", cascade="all, delete-orphan")
    coin_transactions = relationship("CoinTransaction", back_populates="user", cascade="all, delete-orphan")

    # Helper properties for easier access
    @property
    def followers(self):
        return [rel.following for rel in self.followers]
    
    @property
    def following(self):
        return [rel.followed for rel in self.followed_relationships]

    # Blocking relationships
    blocks_made = relationship(
        "Block",
        foreign_keys="Block.blocker_id",
        back_populates="blocker",
        cascade="all, delete-orphan"
    )
    blocks_received = relationship(
        "Block",
        foreign_keys="Block.blocked_id",
        back_populates="blocked",
        cascade="all, delete-orphan"
    )

    # Advertisements
    advertisements = relationship(
        "Advertisement", 
        foreign_keys="Advertisement.user_id",
        back_populates="user",
        lazy="selectin"
    )
    admin_approved_ads = relationship(
        "Advertisement", 
        foreign_keys="Advertisement.admin_id",
        back_populates="admin",
        lazy="selectin"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.profile_picture:
            self.profile_picture = f"https://ui-avatars.com/api/?name={self.username}&background=random"
        # Initialize coin balance if not exists
        if not hasattr(self, 'coin_balance') or not self.coin_balance:
            self.coin_balance = UserCoin(user=self, balance=0)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"

    def verify_password(self, plain_password):
        return pwd_context.verify(plain_password, self.hashed_password)

    def verify_app_lock_password(self, plain_password):
        if not self.app_lock_password:
            return False
        return pwd_context.verify(plain_password, self.app_lock_password)
