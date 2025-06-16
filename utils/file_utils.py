import os
import uuid
from fastapi import UploadFile, HTTPException, status
from typing import Tuple, Optional
import mimetypes
from models.message import MessageType

# Supported file types and their corresponding message types
SUPPORTED_FILE_TYPES = {
    "image": {
        "extensions": {"jpg", "jpeg", "png", "gif", "webp"},
        "message_type": MessageType.IMAGE
    },
    "video": {
        "extensions": {"mp4", "webm", "mov", "avi", "mkv"},
        "message_type": MessageType.VIDEO
    },
    "audio": {
        "extensions": {"mp3", "wav", "ogg", "m4a"},
        "message_type": MessageType.AUDIO
    },
    "document": {
        "extensions": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"},
        "message_type": MessageType.DOCUMENT
    },
    "archive": {
        "extensions": {"zip", "rar", "7z", "tar", "gz"},
        "message_type": MessageType.FILE
    }
}

# Maximum file size in bytes (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Base upload directory
UPLOAD_DIR = "uploads/messages"


def get_file_type(filename: str) -> Tuple[Optional[str], Optional[MessageType]]:
    """
    Determine the file type and corresponding message type based on file extension.
    Returns (file_type, message_type)
    """
    # Get file extension
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    
    # Check each supported file type
    for file_type, info in SUPPORTED_FILE_TYPES.items():
        if ext in info["extensions"]:
            return file_type, info["message_type"]
    
    # Default to file type if extension not recognized
    return "file", MessageType.FILE


async def save_upload_file(upload_file: UploadFile) -> dict:
    """
    Save an uploaded file to the server and return file information.
    """
    # Validate file size
    contents = await upload_file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )
    
    # Get file information
    file_ext = upload_file.filename.split('.')[-1].lower() if '.' in upload_file.filename else ''
    file_type, message_type = get_file_type(upload_file.filename)
    file_name = f"{uuid.uuid4()}.{file_ext}"
    
    # Create upload directory if it doesn't exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Save file
    file_path = os.path.join(UPLOAD_DIR, file_name)
    with open(file_path, "wb") as buffer:
        buffer.write(contents)
    
    return {
        "file_name": upload_file.filename,
        "file_path": file_path,
        "file_url": f"/{file_path}",
        "file_type": file_type,
        "message_type": message_type,
        "file_size": len(contents)
    }


def delete_file(file_path: str) -> bool:
    """
    Delete a file from the server.
    Returns True if file was deleted, False otherwise.
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception:
        pass
    return False
