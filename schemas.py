from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List
from datetime import datetime, timedelta
from app.models.follow_request import FollowRequestStatus

# User schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    model_config = ConfigDict(
        json_schema_extra={"example": {"username": "john_doe", "email": "john@example.com"}}
    )
class UserCreate(UserBase):
    password: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"username": "john_doe", "email": "john@example.com", "password": "strongpassword123"}}
    )
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
class User(UserBase):
    id: int
    is_admin: bool
    bio: Optional[str] = None
    website: Optional[str] = None
    profile_picture: Optional[str] = None
    is_private: bool
    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserBase):
    id: int
    profile_picture_url: Optional[str] = None
    bio: Optional[str] = None
    is_private: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PrivateUserResponse(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_private: bool = True
    model_config = ConfigDict(from_attributes=True)

# Post
class PostBase(BaseModel):
    body: str
    image: Optional[str] = None
    video: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={"example": {"body": "Bu mening birinchi postim!", "image": "post.jpg", "video": None}}
    )
class Post(PostBase):
    id: int
    user_id: int
    is_ad: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# PostSave
class PostSave(BaseModel):
    id: int
    user_id: int
    post_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
class PostSaveCreate(BaseModel):
    user_id: int
    post_id: int
    model_config = ConfigDict(
        json_schema_extra={"example": {"user_id": 1, "post_id": 2}}
    )

# PostView
class PostView(BaseModel):
    id: int
    user_id: int
    post_id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

# Comment
class CommentBase(BaseModel):
    body: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"body": "Zo‘r post!"}}
    )
class Comment(CommentBase):
    id: int
    post_id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Like
class Like(BaseModel):
    id: int
    user_id: int
    post_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
class LikeCreate(BaseModel):
    user_id: int
    post_id: int
    model_config = ConfigDict(
        json_schema_extra={"example": {"user_id": 1, "post_id": 2}}
    )

# Reel
class ReelBase(BaseModel):
    video: str
    caption: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={"example": {"video": "reel1.mp4", "caption": "Bu mening birinchi reel videom!"}}
    )
class Reel(ReelBase):
    id: int
    user_id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

# Follow
class Follow(BaseModel):
    id: int
    follower_id: int
    following_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
class FollowCreate(BaseModel):
    follower_id: int
    following_id: int
    model_config = ConfigDict(
        json_schema_extra={"example": {"follower_id": 1, "following_id": 2}}
    )

class FollowResponse(BaseModel):
    id: int
    follower_id: int
    following_id: int
    created_at: datetime
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "follower_id": 1,
                "following_id": 2,
                "created_at": "2023-01-01T00:00:00"
            }
        }
    )

class FollowRequestResponse(BaseModel):
    id: int
    requester: UserResponse
    status: FollowRequestStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Message
class MessageBase(BaseModel):
    from_user_id: int
    to_user_id: int
    content: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"from_user_id": 1, "to_user_id": 2, "content": "Salom!"}}
    )
class Message(MessageBase):
    id: int
    created_at: datetime
    is_read: bool

    class Config:
        from_attributes = True

# Group
class GroupBase(BaseModel):
    name: str
    image: Optional[str] = None
    creator_id: int
    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "My Group", "image": "group.jpg", "creator_id": 1}}
    )

class GroupCreate(GroupBase):
    pass
class Group(GroupBase):
    id: int
    creator_id: int
    created_at: datetime
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class GroupMember(BaseModel):
    id: int
    group_id: int
    user_id: int
    joined_at: datetime
    model_config = ConfigDict(from_attributes=True)

class GroupAdmin(BaseModel):
    id: int
    group_id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)

class GroupMessageBase(BaseModel):
    from_user_id: int
    text: Optional[str] = None
    post_id: Optional[int] = None
    image: Optional[str] = None
    video: Optional[str] = None
    sticker_id: Optional[int] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "from_user_id": 1,
                "text": "Salom guruh!", 
                "post_id": None, 
                "image": None, 
                "video": None, 
                "sticker_id": None
            }
        }
    )

class GroupMessageCreate(GroupMessageBase):
    pass
class GroupMessage(GroupMessageBase):
    id: int
    group_id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class StickerBase(BaseModel):
    name: str
    image: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Smile", "image": "smile.png"}}
    )
class Sticker(StickerBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class GroupSticker(BaseModel):
    id: int
    group_id: int
    sticker_id: int
    model_config = ConfigDict(from_attributes=True)

# Story
class StoryBase(BaseModel):
    image: Optional[str] = None
    video: Optional[str] = None
    text: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={"example": {"image": "story.jpg", "video": None, "text": "Story matni"}}
    )
class Story(StoryBase):
    id: int
    user_id: int
    created_at: datetime
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class StoryLike(BaseModel):
    id: int
    user_id: int
    story_id: int
    model_config = ConfigDict(from_attributes=True)
class StoryLikeCreate(BaseModel):
    user_id: int
    story_id: int
    model_config = ConfigDict(
        json_schema_extra={"example": {"user_id": 1, "story_id": 2}}
    )

class StoryCommentBase(BaseModel):
    text: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"text": "Ajoyib story!"}}
    )
class StoryComment(StoryCommentBase):
    id: int
    user_id: int
    story_id: int
    model_config = ConfigDict(from_attributes=True)

class StoryView(BaseModel):
    id: int
    user_id: int
    story_id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class ChannelBase(BaseModel):
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "My Channel", "description": "Channel description", "image": "channel.jpg"}}
    )

class ChannelCreate(ChannelBase):
    creator_id: int
    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "My Channel", "description": "Channel description", "image": "channel.jpg", "creator_id": 1}}
    )

class Channel(ChannelBase):
    id: int
    creator_id: int
    created_at: datetime
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class ChannelMessageBase(BaseModel):
    text: Optional[str] = None
    image: Optional[str] = None
    video: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Check out our new post!",
                "image": "post.jpg",
                "video": None
            }
        }
    )

class ChannelMessageCreate(ChannelMessageBase):
    pass

class ChannelMessage(ChannelMessageBase):
    id: int
    channel_id: int
    from_user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ChannelCommentBase(BaseModel):
    text: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"text": "Great post!"}}
    )

class ChannelCommentCreate(ChannelCommentBase):
    pass

class ChannelComment(ChannelCommentBase):
    id: int
    message_id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ChannelSubscriber(BaseModel):
    id: int
    channel_id: int
    user_id: int
    subscribed_at: datetime
    model_config = ConfigDict(from_attributes=True)

class Notification(BaseModel):
    id: int
    user_id: int
    message: str
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AdvertisementBase(BaseModel):
    post_id: int
    link: str
    budget: int = Field(ge=1, le=1000, description="Budget in USD (1-1000)")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "post_id": 1,
                "link": "https://example.com",
                "budget": 10
            }
        }
    )

class AdvertisementCreate(AdvertisementBase):
    pass

class Advertisement(BaseModel):
    id: int
    title: str
    target_url: str
    is_active: bool
    created_at: datetime
    user_id: int

    class Config:
        from_attributes = True

class AdvertisementApprove(BaseModel):
    is_approved: bool
    model_config = ConfigDict(
        json_schema_extra={"example": {"is_approved": True}}
    )

class AdvertisementStats(BaseModel):
    total_views: int
    remaining_views: int
    spent_budget: float
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

# App Lock Schemas
class AppLockPasswordSet(BaseModel):
    password: str = Field(..., min_length=4)

class AppLockPasswordVerify(BaseModel):
    password: str

# LiveStream Schemas
class LiveStreamBase(BaseModel):
    pass

class LiveStreamCreate(LiveStreamBase):
    pass

class LiveStream(LiveStreamBase):
    id: int
    host_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str
    viewer_count: int

    class Config:
        from_attributes = True

class LiveStreamLike(BaseModel):
    id: int
    user_id: int
    livestream_id: int

    class Config:
        from_attributes = True

class LiveStreamComment(BaseModel):
    id: int
    user_id: int
    livestream_id: int
    text: str
    created_at: datetime

    class Config:
        from_attributes = True

# Password Reset Schemas
class PasswordResetRequest(BaseModel):
    email: EmailStr
    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "user@example.com"}}
    )


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=8, max_length=8, pattern=r'^\d{8}$')
    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "user@example.com", "code": "12345678"}}
    )


class NewPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)
    model_config = ConfigDict(
        json_schema_extra={"example": {"new_password": "new_strong_password_123"}}
    )


class PasswordUpdateRequest(BaseModel):
    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)
    model_config = ConfigDict(
        json_schema_extra={"example": {
            "old_password": "current_password_123",
            "new_password": "new_secure_password_123"
        }}
    )

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "token_type": "bearer"}}
    )
