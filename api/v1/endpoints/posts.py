from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Query, Path
from sqlalchemy import Enum
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import logging

from models import User
from schemas.post import PostBase, PostCreate, PostInDBBase, PostUpdate, PostResponse, PostListResponse, TaskStatusResponse
from schemas.blocked_post import BlockedPostCreate
from services.post_service import PostService
from database import SessionLocal, get_db
from routers.auth import get_current_user


# Create the router at the module level
router = APIRouter(prefix="/posts", tags=["Post Management"])

# Define routes in order of priority
# This ensures that /recommended is matched before any {post_id} routes

@router.get(
    "/recommended", 
    response_model=List[PostResponse],
    summary="Tavsiya etilgan postlar | Recommended posts",
    description="""Sizning faolligingiz va qiziqishlaringiz asosida tavsiya etilgan postlar.
    
    Get posts recommended based on your activity and preferences.
    
    **O'zbek tilida:**
    - Siz yoqtirgan postlarga o'xshash postlar
    - Sizning qiziqishlaringizga mos postlar
    - Avval ko'rgan postlaringizga o'xshash kontent
    """,
    responses={
        200: {"description": "Tavsiya etilgan postlar ro'yxati | List of recommended posts"},
        401: {"description": "Avtorizatsiyadan o'tilmagan | Not authenticated"}
    },
    operation_id="get_public_recommended_posts"
)
async def get_public_recommended_posts(
    skip: int = Query(0, ge=0, description="Number of posts to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of posts to return"),
    db: Session = Depends(get_db)
):
    """
    Get recommended posts based on user activity (public endpoint).
    
    For unauthenticated users, returns random posts.
    For authenticated users, considers likes and preferences.
    """
    post_service = PostService(db)
    try:
        posts = await post_service.get_recommended_posts(
            current_user_id=None,  # No user ID for unauthenticated
            skip=skip,
            limit=limit
        )
        return posts
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommended posts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving recommended posts"
        )

@router.get("/{post_id}", response_model=PostResponse, operation_id="get_single_post_public")
async def get_single_post_public(
    post_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single post by ID (public endpoint).
    Returns the post details including user information, like count, and comments.
    This endpoint is available without authentication.
    """
    try:
        service = PostService(db)
        # For unauthenticated requests, we don't need to pass a user ID
        return await service.get_post(post_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_single_post_public: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the post"
        )
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"

@router.post("/upload-media/", response_model=dict)
async def upload_media(
    file: UploadFile = File(..., description="Media file to upload (image or video)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a media file (image or video) for a post.
    
    Returns the URL of the uploaded media file and its type.
    """
    try:
        post_service = PostService(db)
        result = await post_service.upload_media(file, current_user.id)
        return {"status": "success", "data": result}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error uploading media: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload media"
        )

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a new post with the provided data.
    
    - **media_url**: URL of the uploaded media file (from /upload-media/ endpoint)
    - **media_type**: Type of media ('image' or 'video')
    - **body**: Optional text content of the post
    - **filter_type**: Optional filter to apply (e.g., 'sepia', 'black_and_white')
    - **text_overlay**: Optional text to overlay on the media
    - **text_position**: Position of text overlay (default: 'bottom')
    - **sticker_id**: Optional ID of a sticker to add to the post
    - **location_name**: Optional name of the location
    - **latitude/longitude**: Optional coordinates of the location
    
    At least one of body or media_url must be provided.
    No authentication required.
    """
    try:
        # Validate at least one field is provided
        if not post_data.body and not post_data.media_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of body or media_url must be provided"
            )
            
        # If media_url is provided, media_type must also be provided
        if post_data.media_url and not post_data.media_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="media_type must be provided when media_url is included"
            )
            
        # Create the post with a default user ID (0 for unauthenticated users)
        post_service = PostService(db)
        result = await post_service.create_post(
            post_data=post_data,
            user_id=0,  # Default user ID for unauthenticated users
            background_tasks=background_tasks
        )
        
        return {
            "status": "success",
            "message": "Post created successfully",
            "post_id": result["id"]
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error creating post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create post"
        )

@router.get("/feed", 
    response_model=List[PostResponse],
    summary="Postlarni olish | Get feed posts",
    description="""Foydalanuvchi feed'idagi postlarni sahifalab olish.
    
    Retrieve a paginated list of posts for the user's feed.
    
    **O'zbek tilida:**
    - Postlarni sahifalab olish
    - Foydalanuvchi ID bo'yicha filtrlash
    - Bloklangan postlarni ko'rsatish/ko'rsatmaslik
    """,
    responses={
        200: {"description": "Postlar ro'yxati | List of posts"},
        401: {"description": "Avtorizatsiyadan o'tilmagan | Not authenticated"}
    },
    operation_id="get_feed_posts"
)
async def get_feed(
    skip: int = Query(0, ge=0, description="Number of posts to skip (for pagination)"),
    limit: int = Query(10, ge=1, le=100, description="Number of posts to return (1-100)"),
    user_id: Optional[int] = Query(None, description="Filter posts by user ID"),
    include_blocked: bool = Query(False, description="Include posts that you've blocked"),
    db: Session = Depends(get_db)
):
    """
    Get the main feed of posts.
    
    Returns a list of posts with pagination support. You can filter by user ID
    and choose to include or exclude blocked posts.
    """
    post_service = PostService(db)
    try:
        posts, total = await post_service.get_posts(
            current_user_id=None,  # Pass None for unauthenticated user
            skip=skip, 
            limit=limit, 
            user_id=user_id,
            include_blocked=include_blocked
        )
        return posts
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting feed posts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving feed posts"
        )

@router.get("/{post_id}", response_model=PostResponse, operation_id="get_single_post")
async def get_post(
    post_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single post by ID.
    
    Returns the post details including user information, like count, and comments.
    """
    try:
        service = PostService(db)
        # For unauthenticated requests, we don't need to pass a user ID
        return await service.get_post(post_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_post: {str(e)}")
@router.get("/", response_model=PostListResponse, operation_id="list_all_posts")
async def list_posts(
    user_id: Optional[int] = None,
    limit: int = Query(10, gt=0, le=100, description="Number of posts per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db)
):
    """
    List posts with pagination and optional user filter.
    
    - **user_id**: Filter posts by user ID (optional)
    - **limit**: Number of posts per page (1-100)
    - **offset**: Pagination offset
    """
    post_service = PostService(db)
    try:
        posts, total = await post_service.get_posts(
            current_user_id=None,  # Since we removed authentication
            skip=offset,
            limit=limit,
            user_id=user_id
        )
        
        # Calculate pagination info
        page = (offset // limit) + 1
        pages = (total + limit - 1) // limit
        
        return PostListResponse(
            items=posts,
            total=total,
            page=page,
            pages=pages
        )
    except Exception as e:
        logger.error(f"Error in list_posts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving posts"
        )

@router.get(
    "/recommended", 
    response_model=List[PostResponse],
    summary="Tavsiya etilgan postlar | Recommended posts",
    description="""Sizning faolligingiz va qiziqishlaringiz asosida tavsiya etilgan postlar.
    
    Get posts recommended based on your activity and preferences.
    
    **O'zbek tilida:**
    - Siz yoqtirgan postlarga o'xshash postlar
    - Sizning qiziqishlaringizga mos postlar
    - Avval ko'rgan postlaringizga o'xshash kontent
    """,
    responses={
        200: {"description": "Tavsiya etilgan postlar ro'yxati | List of recommended posts"},
        401: {"description": "Avtorizatsiyadan o'tilmagan | Not authenticated"}
    },
    operation_id="get_recommended_posts"
)
async def get_recommended_posts(
    skip: int = Query(0, ge=0, description="Number of posts to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of posts to return"),
    db: Session = Depends(get_db)
):
    """
    Get recommended posts based on user activity.
    
    For unauthenticated users, returns random posts.
    For authenticated users, considers likes and preferences.
    """
    post_service = PostService(db)
    try:
        # For unauthenticated users, just get random posts
        posts, _ = await post_service.get_posts(
            current_user_id=None,  # No user ID for unauthenticated
            skip=skip,
            limit=limit,
            include_blocked=False
        )
        return posts
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommended posts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving recommended posts"
        )

@router.get("/user/recommended", response_model=List[PostResponse], operation_id="get_user_recommended_posts")
async def get_user_recommended_posts(
    skip: int = Query(0, ge=0, description="Number of posts to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of posts to return"),
    db: Session = Depends(get_db)
):
    """
    Get recommended posts for a user.
    
    Returns a list of posts recommended based on the user's activity and preferences.
    """
    post_service = PostService(db)
    try:
        # For unauthenticated users, just get random posts
        posts, _ = await post_service.get_posts(
            current_user_id=None,  # No user ID for unauthenticated
            skip=skip,
            limit=limit,
            include_blocked=False
        )
        return posts
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommended posts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving recommended posts"
        )

@router.get("/user/{post_id}", response_model=PostResponse, operation_id="get_user_post")
async def get_user_post(
    post_id: int,
    current_user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get a single post by ID for a user.
    
    Get a single post by ID.
    Returns the post details including user information, like count, and comments.
    """
    try:
        service = PostService(db)
        # For unauthenticated requests, we don't need to pass a user ID
        return await service.get_post(post_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the post"
        )

@router.post("/{post_id}/block/", 
             response_model=dict, 
             status_code=status.HTTP_200_OK,
             summary="Block a post",
             description="Block a specific post to prevent it from appearing in your feed. Other users will still be able to see the post. No authentication required.",
             response_description="Status of the block operation",
             operation_id="block_post"
)
async def block_post(
    post_id: int = Path(..., description="The ID of the post to block"),
    block_data: BlockedPostCreate = None,
    db: Session = Depends(get_db)
):
    # Use a default user ID when not authenticated
    current_user_id = 0  # Default user ID for unauthenticated users
    """
    Block a specific post.
    
    This will prevent the post from appearing in your feed.
    Other users will still be able to see the post.
    
    - **post_id**: The ID of the post to block
    - **reason**: Optional reason for blocking the post
    
    Returns a success message if the post was blocked successfully.
    """
    try:
        post_service = PostService(db)
        result = await post_service.block_post(
            post_id=post_id,
            user_id=current_user_id,
            reason=block_data.reason if block_data else None
        )
        return {
            "status": "success",
            "message": "Post blocked successfully",
            "post_id": post_id
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error blocking post {post_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while blocking the post"
        )

@router.get("/{post_id}/block/status/", 
             response_model=dict, 
             status_code=status.HTTP_200_OK,
             summary="Check post block status",
             description="Check if a post is blocked. No authentication required.",
             response_description="Block status of the post",
             operation_id="get_post_block_status"
)
async def get_post_block_status(
    post_id: int = Path(..., description="The ID of the post to check"),
    db: Session = Depends(get_db)
):
    # Use a default user ID when not authenticated
    current_user_id = 0  # Default user ID for unauthenticated users
    """
    Check if a post is blocked by the current user.
    
    - **post_id**: The ID of the post to check
    
    Returns a boolean indicating whether the post is blocked by the current user.
    """
    try:
        post_service = PostService(db)
        is_blocked = await post_service.is_post_blocked(
            post_id=post_id,
            user_id=current_user_id
        )
        
        return {
            "status": "success",
            "post_id": post_id,
            "is_blocked": is_blocked,
            "message": "Post is blocked" if is_blocked else "Post is not blocked"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error checking block status for post {post_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while checking post block status"
        )

@router.post("/{post_id}/unblock/", 
             response_model=dict, 
             status_code=status.HTTP_200_OK,
             summary="Unblock a post",
             description="Unblock a previously blocked post to allow it to appear in your feed again. No authentication required.",
             response_description="Status of the unblock operation",
             operation_id="unblock_post"
)
async def unblock_post(
    post_id: int = Path(..., description="The ID of the post to unblock"),
    db: Session = Depends(get_db)
):
    # Use a default user ID when not authenticated
    current_user_id = 0  # Default user ID for unauthenticated users
    """
    Unblock a previously blocked post.
    
    This will allow the post to appear in your feed again.
    
    - **post_id**: The ID of the post to unblock
    
    Returns a success message if the post was unblocked successfully.
    """
    try:
        post_service = PostService(db)
        result = await post_service.unblock_post(
            post_id=post_id,
            user_id=current_user_id
        )
        return {
            "status": "success",
            "message": "Post unblocked successfully",
            "post_id": post_id
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error unblocking post {post_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unblocking the post"
        )

@router.put("/{post_id}", response_model=PostResponse, operation_id="update_post")
async def update_post(
    post_id: int,
    post_update: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing post.
    
    Only the post author can update the post.
    """
    try:
        service = PostService(db)
        return await service.update_post(
            post_id=post_id,
            post_data=post_update,
            current_user_id=current_user.id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the post"
        )

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a post.
    
    Only the post author can delete the post.
    
    :param post_id: The ID of the post to delete
    :return: None
    """
    try:
        service = PostService(db)
        await service.delete_post(post_id, current_user.id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_post: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the post"
        )

@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def check_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check the status of a background task.
    
    Use this endpoint to check the status of a post creation task.
    """
    try:
        from services.task_queue import task_queue
        
        task_status = await task_queue.get_task_status(task_id)
        if not task_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
            
        return {
            "task_id": task_id,
            "status": task_status,
            "result": None,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error checking task status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while checking task status"
        )

# Export the router to be included in the API
# The router is already created at the top of the file with the prefix "/posts"
