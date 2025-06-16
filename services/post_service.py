import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple


from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.query import Query
from sqlalchemy import or_, and_, func
from fastapi import HTTPException, status, UploadFile, Depends, Query
from fastapi.security import OAuth2PasswordBearer
import shutil
import logging
import random
import json

from utils.crypto_utils import encrypt_data, decrypt_data, encrypt_dict, decrypt_dict

from models import User, Post, Block
from models.like import Like
from schemas.post import PostBase, PostCreate, PostInDBBase, PostUpdate, PostResponse, PostListResponse
from schemas.blocked_post import BlockedPostCreate, BlockedPost
from utils.media_handler import MediaHandler
from config import settings

# For JWT token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

logger = logging.getLogger(__name__)

class PostService:
    """Service for handling post-related operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.media_handler = MediaHandler(settings.MEDIA_ROOT)
    
    async def _apply_media_enhancements(
        self,
        file_path: str,
        media_type: str,
        filter_type: Optional[str] = None,
        text_overlay: Optional[str] = None,
        text_position: str = "bottom",
        sticker_id: Optional[int] = None
    ) -> str:
        """
        Apply enhancements to media file (filters, text, stickers).
        
        Args:
            file_path: Path to the media file
            media_type: Type of media ('image' or 'video')
            filter_type: Optional filter to apply
            text_overlay: Optional text to overlay
            text_position: Position of the text overlay
            sticker_id: Optional sticker ID to add
            
        Returns:
            Path to the enhanced media file
            
        Note:
            This is a placeholder implementation. In a real application,
            you would use libraries like Pillow for images and MoviePy
            for videos to apply these effects.
        """
        try:
            # In a real implementation, you would:
            # 1. Load the media file
            # 2. Apply filter if specified
            # 3. Add text overlay if specified
            # 4. Add sticker if specified
            # 5. Save the enhanced media
            
            # For now, we'll just return the original path
            # In a real app, you would process the file and return the new path
            return file_path
            
        except Exception as e:
            logger.error(f"Error applying media enhancements: {str(e)}")
            # Return original path if enhancement fails
            return file_path
    
    async def _save_media_file(
        self,
        file: UploadFile,
        user_id: int,
        media_type: str
    ) -> str:
        """
        Save an uploaded media file and return its URL.
        
        Args:
            file: Uploaded file
            user_id: ID of the user uploading the file
            media_type: Type of media ('image' or 'video')
            
        Returns:
            URL of the saved media file
        """
        try:
            # Generate a unique filename
            file_ext = os.path.splitext(file.filename or 'media')[1] or (
                '.jpg' if media_type == 'image' else '.mp4'
            )
            filename = f"{uuid.uuid4()}{file_ext}"
            
            # Create user-specific directory if it doesn't exist
            user_dir = os.path.join(settings.MEDIA_ROOT, 'posts', str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Save the file
            file_path = os.path.join(user_dir, filename)
            with open(file_path, 'wb') as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            # Return the relative URL
            return f"/media/posts/{user_id}/{filename}"
            
        except Exception as e:
            logger.error(f"Error saving media file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save media file"
            )
    
    async def upload_media(
        self,
        file: UploadFile,
        user_id: int
    ) -> Dict[str, str]:
        """
        Upload a media file (image or video) and return its URL.
        
        Args:
            file: Uploaded file
            user_id: ID of the user uploading the file
            
        Returns:
            Dictionary with media URL and type
        """
        try:
            # Validate file type
            content_type = file.content_type or ''
            if content_type.startswith('image/'):
                media_type = 'image'
            elif content_type.startswith('video/'):
                media_type = 'video'
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported file type. Only images and videos are allowed."
                )
            
            # Save the file
            media_url = await self._save_media_file(file, user_id, media_type)
            
            return {
                "media_url": media_url,
                "media_type": media_type
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error uploading media: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload media"
            )
    
    async def _process_post_media(
        self,
        post_id: int,
        media_url: str,
        media_type: str,
        filter_type: Optional[str] = None,
        text_overlay: Optional[str] = None,
        text_position: str = "bottom",
        sticker_id: Optional[int] = None
    ) -> None:
        """
        Process post media in the background.
        
        This method applies filters, text overlays, and stickers to the media
        and updates the post with the processed media URL.
        """
        try:
            # In a real implementation, this would:
            # 1. Download the media from media_url
            # 2. Apply the specified enhancements
            # 3. Upload the processed media
            # 4. Update the post with the new media URL
            
            # For now, we'll just log that processing would happen here
            logger.info(f"Processing media for post {post_id}")
            
        except Exception as e:
            logger.error(f"Error processing media for post {post_id}: {str(e)}")
    
    async def create_post(
        self,
        post_data: PostCreate,
        user_id: int,
        background_tasks = None
    ) -> Dict[str, Any]:
        """
        Create a new post with the provided data.
        
        Args:
            post_data: Post data including media and enhancement options
            user_id: ID of the post author
            background_tasks: FastAPI background tasks for async processing
            
        Returns:
            Dictionary with the created post ID
        """
        try:
            # Create post in database
            db_post = Post(
                content=post_data.body,
                media_url=post_data.media_url,
                media_type=post_data.media_type,
                user_id=user_id,
                latitude=post_data.latitude,
                longitude=post_data.longitude,
                location_name=post_data.location_name,
                filter_type=post_data.filter_type,
                text_overlay=post_data.text_overlay,
                text_position=post_data.text_position or "bottom",
                sticker_id=post_data.sticker_id,
                is_encrypted=False  # Will be set to True after encryption if needed
            )
            
            self.db.add(db_post)
            self.db.flush()  # Flush to get the post ID
            
            # Reward user with 1 coin for creating a post
            from services.sticker_service import StickerService
            sticker_service = StickerService(self.db)
            try:
                await sticker_service.reward_for_post(user_id)
            except Exception as e:
                logger.error(f"Failed to reward user for post creation: {str(e)}")
                # Don't fail the post creation if coin reward fails
                
            self.db.commit()
            self.db.refresh(db_post)
            
            # Schedule background processing if needed
            if background_tasks and post_data.media_url and post_data.media_type:
                background_tasks.add_task(
                    self._process_post_media,
                    post_id=db_post.id,
                    media_url=post_data.media_url,
                    media_type=post_data.media_type,
                    filter_type=post_data.filter_type,
                    text_overlay=post_data.text_overlay,
                    text_position=post_data.text_position or "bottom",
                    sticker_id=post_data.sticker_id
                )
            
            return {"id": db_post.id}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating post: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e) or "An error occurred while creating the post"
            )
    
    async def _get_post_with_permissions(self, post_id: int, current_user_id: int) -> Post:
        """
        Get a post by ID with permission checks.
        
        Args:
            post_id: ID of the post to retrieve
            current_user_id: ID of the current user for permissions
            
        Returns:
            Post model instance
            
        Raises:
            HTTPException: If post not found or user doesn't have permission
        """
        # Eager load relationships to avoid N+1 queries
        post = self.db.query(Post)\
            .options(
                joinedload(Post.owner),
                joinedload(Post.likes),
                joinedload(Post.comments)
            )\
            .filter(Post.id == post_id)\
            .first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
            
        # Check if the post is blocked by or for the current user
        # This would be implemented based on your blocking logic
        # For example:
        # if await self._is_post_blocked(post_id, current_user_id):
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="This post is not available"
        #     )
            
        return post
    
    async def get_post(self, post_id: int, current_user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get a single post by ID with all related data.
        
        Args:
            post_id: ID of the post to retrieve
            current_user_id: ID of the current user for permissions and like status
            
        Returns:
            Dictionary with post details and related data
            
        Raises:
            HTTPException: If post not found or permission denied
        """
        try:
            # Get post with permission checks
            post = await self._get_post_with_permissions(post_id, current_user_id)
            
            # For unauthenticated users, set default values
            is_liked = False
            can_edit = False
            can_delete = False
            
            # If authenticated, check if user has liked this post
            if current_user_id:
                is_liked = any(like.user_id == current_user_id for like in post.likes) if post.likes else False
                can_edit = post.user_id == current_user_id
                can_delete = post.user_id == current_user_id
            
            # Convert post to dictionary with owner relationship
            post_data = post.to_dict(include_user=True)
            
            # If owner is None, create a default user object
            if not post.owner:
                post_data['user'] = {
                    'id': None,
                    'username': 'deleted_user',
                    'avatar_url': None,
                    'is_verified': False
                }
            
            post_data.update({
                'is_liked': is_liked,
                'is_saved': False,  # Will be set based on user's saved posts
                'can_edit': can_edit,
                'can_delete': can_delete,
            })
            
            return post_data
            
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Error getting post {post_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving the post"
            )
    
    def _get_posts_query(
        self,
        user_id: Optional[int] = None,
        include_blocked: bool = False,
        current_user_id: Optional[int] = None
    ) -> Query:
        """
        Get the base query for listing posts with optional filters.
        
        Args:
            user_id: Filter posts by user ID (optional)
            include_blocked: Whether to include blocked posts (default: False)
            current_user_id: ID of the current user (None for unauthenticated)
            
        Returns:
            SQLAlchemy query object with joined relationships
        """
        query = self.db.query(Post).options(
            joinedload(Post.owner),
            joinedload(Post.likes),
            joinedload(Post.comments)
        )
        
        # Apply user filter if provided
        if user_id is not None:
            query = query.filter(Post.user_id == user_id)
            
        # For unauthenticated users, just show all posts
        if current_user_id is None:
            return query
            
        # For authenticated users, filter out blocked posts unless explicitly requested
        if not include_blocked:
            # Get blocked posts for the current user
            blocked_posts = self.db.query(BlockedPost).filter(
                BlockedPost.user_id == current_user_id
            ).all()
            
            # Get blocked user IDs
            blocked_user_ids = self.db.query(Block).filter(
                Block.blocker_id == current_user_id
            ).all()
            
            # Filter out blocked posts and users
            if blocked_posts or blocked_user_ids:
                blocked_post_ids = [bp.post_id for bp in blocked_posts]
                blocked_user_ids = [b.blocked_id for b in blocked_user_ids]
                
                query = query.filter(
                    ~Post.id.in_(blocked_post_ids),
                    ~Post.user_id.in_(blocked_user_ids)
                )
            
        return query
    
    async def get_posts(
        self,
        current_user_id: Optional[int],
        skip: int = 0,
        limit: int = 10,
        user_id: Optional[int] = None,
        include_blocked: bool = False
    ) -> Tuple[List[PostResponse], int]:
        """
        List posts with pagination and optional user filter.
        
        Args:
            user_id: Filter posts by user ID (optional)
            limit: Number of posts per page (max 50)
            offset: Pagination offset
            current_user_id: ID of the current user for like status
            
        Returns:
            Tuple with list of posts and total count
            
        Raises:
            HTTPException: If there's an error retrieving posts
        """
        try:
            # Validate pagination parameters
            limit = min(max(1, limit), 50)  # Enforce max limit of 50
            offset = max(0, skip)
            
            # Get the base query with filters
            query = self._get_posts_query(
                user_id=user_id,
                include_blocked=include_blocked,
                current_user_id=current_user_id
            )
            
            # Get total count for pagination
            total = query.count()
            
            # Mix ordered and random posts
            # Get 70% of posts in chronological order
            ordered_count = int(limit * 0.7)
            ordered_posts = query.order_by(Post.created_at.desc())\
                                .offset(offset)\
                                .limit(ordered_count)\
                                .all()
            
            # Get remaining posts randomly
            random_count = limit - len(ordered_posts)
            if random_count > 0:
                random_posts = query.order_by(func.random())\
                                  .offset(offset)\
                                  .limit(random_count)\
                                  .all()
                posts = ordered_posts + random_posts
            else:
                posts = ordered_posts
            
            # Shuffle the final list to mix ordered and random posts
            random.shuffle(posts)
            
            # Get like status for current user
            liked_post_ids = set()
            if current_user_id and posts:
                post_ids = [post.id for post in posts]
                liked_posts = self.db.query(Like.post_id).filter(
                    Like.post_id.in_(post_ids),
                    Like.user_id == current_user_id
                ).all()
                liked_post_ids = {post_id for (post_id,) in liked_posts}
            
            # Convert posts to response format
            post_responses = []
            for post in posts:
                post_data = post.to_dict(include_user=True)
                post_data['is_liked'] = post.id in liked_post_ids if current_user_id else False
                post_data['is_saved'] = False
                post_data['can_edit'] = post.user_id == current_user_id if current_user_id else False
                post_data['can_delete'] = post.user_id == current_user_id if current_user_id else False
                post_responses.append(PostResponse(**post_data))
            
            return post_responses, total
            
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Error getting posts: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving posts"
            )
    
    async def update_post(
        self,
        post_id: int,
        post_data: PostUpdate,
        current_user_id: int
    ) -> Dict[str, Any]:
        """
        Update an existing post.
        
        Args:
            post_id: ID of the post to update
            post_data: Updated post data
            current_user_id: ID of the current user for authorization
            
        Returns:
            Dictionary with the updated post data
            
        Raises:
            HTTPException: If post not found, permission denied, or update fails
        """
        try:
            # Get the post with permission checks
            post = await self._get_post_with_permissions(post_id, current_user_id)
            
            # Check if current user is the author
            if post.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to update this post"
                )
            
            # Update post fields from the provided data
            update_data = post_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                # Skip read-only fields
                if field in {'id', 'user_id', 'created_at', 'updated_at'}:
                    continue
                setattr(post, field, value)
            
            post.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(post)
            
            # Return the updated post
            return await self.get_post(post.id, current_user_id)
            
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating post {post_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while updating the post"
            )
    
    def _is_admin(self, user_id: int) -> bool:
        """
        Check if a user is an admin.
        
        Args:
            user_id: ID of the user to check
            
        Returns:
            bool: True if the user is an admin, False otherwise
        """
        # This is a placeholder. In a real app, you would check the user's role
        # For example:
        # user = self.db.query(User).filter(User.id == user_id).first()
        # return user and user.is_admin
        return False
        
    async def block_post(
        self,
        post_id: int,
        user_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Block a post from being viewed by the current user.
        
        Args:
            post_id: ID of the post to block
            user_id: ID of the user blocking the post
            reason: Optional reason for blocking
            
        Returns:
            Dictionary with success message
            
        Raises:
            HTTPException: If post not found or already blocked
        """
        from models.blocked_post import BlockedPost
        
        try:
            # Check if post exists
            post = self.db.query(Post).filter(Post.id == post_id).first()
            if not post:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Post not found"
                )
                
            # Check if already blocked
            existing_block = self.db.query(BlockedPost).filter(
                BlockedPost.post_id == post_id,
                BlockedPost.user_id == user_id
            ).first()
            
            if existing_block:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Post is already blocked"
                )
            
            # Create the block
            blocked_post = BlockedPost(
                post_id=post_id,
                user_id=user_id,
                reason=reason
            )
            
            self.db.add(blocked_post)
            self.db.commit()
            
            return {"message": "Post blocked successfully"}
            
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error blocking post {post_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while blocking the post"
            )
    
    async def unblock_post(
        self,
        post_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Unblock a previously blocked post.
        
        Args:
            post_id: ID of the post to unblock
            user_id: ID of the user unblocking the post
            
        Returns:
            Dictionary with success message
            
        Raises:
            HTTPException: If post not found or not blocked
        """
        from models.blocked_post import BlockedPost
        
        try:
            # Check if block exists
            blocked_post = self.db.query(BlockedPost).filter(
                BlockedPost.post_id == post_id,
                BlockedPost.user_id == user_id
            ).first()
            
            if not blocked_post:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Post is not blocked"
                )
            
            # Remove the block
            self.db.delete(blocked_post)
            self.db.commit()
            
            return {"message": "Post unblocked successfully"}
            
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error unblocking post {post_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while unblocking the post"
            )
    
    async def get_recommended_posts(
        self,
        current_user_id: Optional[int],
        skip: int = 0,
        limit: int = 10
    ) -> List[PostResponse]:
        """
        Get recommended posts for a user.
        
        For unauthenticated users, returns random posts.
        For authenticated users, considers likes and preferences.
        
        Args:
            current_user_id: ID of the current user (None for unauthenticated)
            skip: Number of posts to skip
            limit: Number of posts to return
            
        Returns:
            List of recommended posts
        """
        try:
            # Get all posts
            posts_query = self._get_posts_query(
                user_id=None,  # Don't filter by user
                include_blocked=False,
                current_user_id=current_user_id
            )
            
            # Get total count for pagination
            total = posts_query.count()
            
            # For authenticated users, get posts based on preferences
            if current_user_id:
                # Get posts liked by the user
                liked_posts = self.db.query(Post.id).join(Like).filter(
                    Like.user_id == current_user_id
                ).all()
                
                liked_post_ids = [post_id for (post_id,) in liked_posts]
                
                # Get posts that are similar to liked posts
                if liked_post_ids:
                    recommended_query = posts_query.filter(
                        Post.id.in_(liked_post_ids)
                    ).order_by(func.random())
                else:
                    # If no likes, just get random posts
                    recommended_query = posts_query.order_by(func.random())
            else:
                # For unauthenticated users, just get random posts
                recommended_query = posts_query.order_by(func.random())
            
            # Apply pagination
            posts = recommended_query.offset(skip).limit(limit).all()
            
            # Convert to response format
            post_responses = []
            for post in posts:
                post_data = post.to_dict(include_user=True)
                post_data['is_liked'] = False  # Default for unauthenticated users
                post_data['is_saved'] = False
                post_data['can_edit'] = False
                post_data['can_delete'] = False
                post_responses.append(PostResponse(**post_data))
            
            return post_responses
            
        except Exception as e:
            logger.error(f"Error getting recommended posts: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving recommended posts"
            )

    async def is_post_blocked(
        self,
        post_id: int,
        user_id: int
    ) -> bool:
        """
        Check if a post is blocked by the current user.
        
        Args:
            post_id: ID of the post to check
            user_id: ID of the user to check
            
        Returns:
            bool: True if the post is blocked by the user, False otherwise
        """
        from models.blocked_post import BlockedPost
        
        return self.db.query(
            self.db.query(BlockedPost)
            .filter(
                BlockedPost.post_id == post_id,
                BlockedPost.user_id == user_id
            )
            .exists()
        ).scalar()
    
    async def delete_post(self, post_id: int, current_user_id: int) -> Dict[str, Any]:
        """
        Delete a post.
        
        Args:
            post_id: ID of the post to delete
            current_user_id: ID of the current user for authorization
            
        Returns:
            Dictionary with success message
            
        Raises:
            HTTPException: If post not found, permission denied, or deletion fails
        """
        try:
            # Get the post with permission checks
            post = await self._get_post_with_permissions(post_id, current_user_id)
            
            # Check if current user is the author or an admin
            if post.user_id != current_user_id and not self._is_admin(current_user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to delete this post"
                )
            
            # In a real app, you might want to soft delete instead
            self.db.delete(post)
            self.db.commit()
            
            return {"message": "Post deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting post: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while deleting the post"
            )
