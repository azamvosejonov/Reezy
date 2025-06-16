import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, Tuple, BinaryIO, List, Dict, Any
from fastapi import UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps
import magic
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MediaHandler:
    """
    Handles media file uploads, processing, and storage.
    """
    
    # Allowed MIME types
    ALLOWED_IMAGE_TYPES = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp'
    ]
    
    ALLOWED_VIDEO_TYPES = [
        'video/mp4',
        'video/quicktime',
        'video/x-msvideo',
        'video/x-ms-wmv',
        'video/x-flv',
        'video/webm'
    ]
    
    # File size limits in bytes
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB
    
    # Thumbnail settings
    THUMBNAIL_SIZE = (320, 320)
    
    def __init__(self, base_upload_dir: str):
        """
        Initialize the media handler.
        
        Args:
            base_upload_dir: Base directory for uploads (e.g., 'media')
        """
        self.base_upload_dir = Path(base_upload_dir)
        self.ensure_directories()
    
    def ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.base_upload_dir / 'posts',
            self.base_upload_dir / 'videos',
            self.base_upload_dir / 'thumbnails',
            self.base_upload_dir / 'temp'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def save_uploaded_file(
        self, 
        file: UploadFile,
        file_type: str = 'image',
        user_id: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Save an uploaded file with validation and processing.
        
        Args:
            file: The uploaded file
            file_type: Type of file ('image' or 'video')
            user_id: Optional user ID for organizing uploads
            
        Returns:
            Dict containing file paths and metadata
        """
        # Validate file type
        content_type = await self._get_content_type(file)
        
        if file_type == 'image' and content_type not in self.ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image type. Allowed types: {', '.join(self.ALLOWED_IMAGE_TYPES)}"
            )
            
        if file_type == 'video' and content_type not in self.ALLOWED_VIDEO_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid video type. Allowed types: {', '.join(self.ALLOWED_VIDEO_TYPES)}"
            )
        
        # Validate file size
        file_size = await self._get_file_size(file)
        max_size = self.MAX_IMAGE_SIZE if file_type == 'image' else self.MAX_VIDEO_SIZE
        
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max size: {max_size / (1024 * 1024)}MB"
            )
        
        # Generate unique filename
        file_ext = Path(file.filename).suffix.lower()
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Create user directory if user_id is provided
        if user_id:
            user_dir = self.base_upload_dir / file_type / str(user_id)
            user_dir.mkdir(parents=True, exist_ok=True)
            file_path = user_dir / unique_filename
        else:
            file_path = self.base_upload_dir / file_type / unique_filename
        
        # Save the file
        temp_path = await self._save_to_temp(file, file_path)
        
        try:
            # Process the file based on type
            if file_type == 'image':
                result = await self._process_image(temp_path, file_path)
            elif file_type == 'video':
                result = await self._process_video(temp_path, file_path)
            else:
                result = {
                    'original_path': str(file_path),
                    'original_url': f"/media/{file_type}/{unique_filename}",
                    'type': 'other'
                }
            
            # Add common metadata
            result.update({
                'filename': file.filename,
                'content_type': content_type,
                'size': file_size,
                'uploaded_at': datetime.utcnow().isoformat()
            })
            
            return result
            
        except Exception as e:
            # Clean up if processing fails
            if file_path.exists():
                file_path.unlink()
            logger.error(f"Error processing file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing file: {str(e)}"
            )
            
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
    
    async def _process_image(
        self, 
        temp_path: Path, 
        output_path: Path
    ) -> Dict[str, str]:
        """Process an uploaded image."""
        try:
            # Open and validate image
            with Image.open(temp_path) as img:
                # Convert to RGB if needed
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Save original
                img.save(output_path, 'JPEG', quality=85, optimize=True, progressive=True)
                
                # Generate thumbnail
                thumbnail_path = self._generate_thumbnail(img, output_path)
                
                return {
                    'original_path': str(output_path),
                    'original_url': f"/media/posts/{output_path.name}",
                    'thumbnail_path': str(thumbnail_path),
                    'thumbnail_url': f"/media/thumbnails/{thumbnail_path.name}",
                    'type': 'image',
                    'width': img.width,
                    'height': img.height
                }
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise
    
    async def _process_video(
        self, 
        temp_path: Path, 
        output_path: Path
    ) -> Dict[str, str]:
        """Process an uploaded video."""
        try:
            # For now, just move the file
            # In production, you might want to:
            # 1. Generate thumbnails
            # 2. Transcode to different qualities
            # 3. Extract metadata
            shutil.move(temp_path, output_path)
            
            # Generate a thumbnail (this is a placeholder - in production use ffmpeg)
            thumbnail_path = self.base_upload_dir / 'thumbnails' / f"{output_path.stem}.jpg"
            
            # Create a black thumbnail as placeholder
            with Image.new('RGB', (320, 180), 'black') as img:
                img.save(thumbnail_path, 'JPEG')
            
            return {
                'original_path': str(output_path),
                'original_url': f"/media/videos/{output_path.name}",
                'thumbnail_path': str(thumbnail_path),
                'thumbnail_url': f"/media/thumbnails/{thumbnail_path.name}",
                'type': 'video'
            }
            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            raise
    
    def _generate_thumbnail(self, image: Image.Image, original_path: Path) -> Path:
        """Generate a thumbnail from an image."""
        try:
            # Create thumbnail
            thumbnail = ImageOps.fit(
                image, 
                self.THUMBNAIL_SIZE, 
                method=Image.Resampling.LANCZOS,
                bleed=0.0,
                centering=(0.5, 0.5)
            )
            
            # Save thumbnail
            thumbnail_path = self.base_upload_dir / 'thumbnails' / f"thumb_{original_path.name}"
            thumbnail.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
            
            return thumbnail_path
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            raise
    
    async def _save_to_temp(self, file: UploadFile, dest_path: Path) -> Path:
        """Save uploaded file to a temporary location."""
        temp_path = self.base_upload_dir / 'temp' / f"temp_{uuid.uuid4()}"
        
        try:
            with open(temp_path, 'wb') as buffer:
                shutil.copyfileobj(file.file, buffer)
            return temp_path
            
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f"Error saving temp file: {str(e)}")
            raise
    
    async def _get_content_type(self, file: UploadFile) -> str:
        """Get the content type of an uploaded file."""
        # First try the content type from the upload
        if file.content_type:
            return file.content_type
        
        # Fall back to magic number detection
        try:
            # Read first 2048 bytes for magic number detection
            chunk = await file.read(2048)
            await file.seek(0)  # Reset file pointer
            
            mime = magic.Magic(mime=True)
            return mime.from_buffer(chunk)
            
        except Exception as e:
            logger.warning(f"Could not determine content type: {str(e)}")
            return 'application/octet-stream'
    
    async def _get_file_size(self, file: UploadFile) -> int:
        """Get the size of an uploaded file."""
        # Save current position
        current_position = file.file.tell()
        
        # Move to end of file
        file.file.seek(0, 2)
        size = file.file.tell()
        
        # Reset position
        file.file.seek(current_position)
        
        return size
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file.
        
        Args:
            file_path: Path to the file to delete
            
        Returns:
            bool: True if file was deleted, False otherwise
        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {str(e)}")
            return False
