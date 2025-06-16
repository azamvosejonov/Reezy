from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from calls.schemas.call import (
    Call, CallCreate, CallUpdate,
    CallTokenResponse, CallSignal, CallWithParticipants
)
from calls.services.call_service import CallService
from calls.services.websocket_manager import connection_manager
from models import User
from database import get_db
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/initiate", response_model=Call)
async def initiate_call(
    call_data: CallCreate,
    db: Session = Depends(get_db)
):
    """
    Initiate a new call without authentication.
    """
    call_service = CallService(db)
    try:
        # Use a default caller ID (e.g., 1) or get it from request data
        caller_id = 1  # You might want to change this based on your needs
        call = await call_service.initiate_call(caller_id, call_data)
        return call
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{call_id}/answer", response_model=Call)
async def answer_call(
    call_id: int,
    db: Session = Depends(get_db)
):
    """
    Answer an incoming call without authentication.
    """
    call_service = CallService(db)
    try:
        # Use a default user ID or get it from request data
        user_id = 1  # You might want to change this based on your needs
        call = call_service.answer_call(call_id, user_id)
        return call
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{call_id}/reject", response_model=Call)
async def reject_call(
    call_id: int,
    db: Session = Depends(get_db)
):
    """
    Reject an incoming call without authentication.
    """
    call_service = CallService(db)
    try:
        # Use a default user ID or get it from request data
        user_id = 1  # You might want to change this based on your needs
        call = call_service.reject_call(call_id, user_id)
        return call
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{call_id}/end", response_model=Call)
async def end_call(
    call_id: int,
    db: Session = Depends(get_db)
):
    """
    End an ongoing call without authentication.
    """
    call_service = CallService(db)
    try:
        # Use a default user ID or get it from request data
        user_id = 1  # You might want to change this based on your needs
        call = call_service.end_call(call_id, user_id)
        # Notify other participants
        await connection_manager.notify_call_status_change(
            call_id, 
            "call_ended",
            initiator_id=user_id
        )
        return call
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/history", response_model=List[Call])
async def get_call_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get call history without authentication.
    Returns all calls (consider adding filters if needed).
    """
    call_service = CallService(db)
    # Return all calls, you might want to add pagination
    return call_service.get_all_calls(limit, offset)

@router.get("/missed", response_model=List[Call])
async def get_missed_calls(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get missed calls without authentication.
    Returns all missed calls (consider adding filters if needed).
    """
    call_service = CallService(db)
    # This is a simplified example - you might want to add filters for missed calls
    return call_service.get_calls(limit=limit, offset=offset, status="missed")

@router.get("/{call_id}", response_model=CallWithParticipants)
async def get_call(
    call_id: int,
    db: Session = Depends(get_db)
):
    """
    Get call details without authentication.
    """
    call_service = CallService(db)
    try:
        # Skip user validation
        call = call_service.get_call(call_id, None)
        return call
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time call signaling.
    No authentication required.
    """
    # Accept all WebSocket connections without authentication
    await websocket.accept()
    
    # Use a temporary user ID for anonymous connections
    # In a real application, you might want to track anonymous users differently
    user_id = f"anonymous_{id(websocket)}"
    
    # Accept the WebSocket connection
    await websocket.accept()
    
    # Connect the user to the WebSocket manager
    await connection_manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive and handle messages
            data = await websocket.receive_json()
            await connection_manager.handle_message(db, user_id, data)
    except WebSocketDisconnect:
        connection_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(user_id)
        raise

@router.post("/{call_id}/signal", status_code=status.HTTP_200_OK)
async def send_signal(
    call_id: int,
    signal_data: CallSignal,
    db: Session = Depends(get_db)
):
    """
    Send a WebRTC signal to other call participants without authentication.
    """
    call_service = CallService(db)
    try:
        # Skip user validation
        call = call_service.get_call(call_id, None)
        
        # Forward the signal to the connection manager
        # Using a default sender ID, adjust as needed
        sender_id = 1
        await connection_manager.handle_message(db, sender_id, {
            "type": "call_signal",
            "call_id": call_id,
            "receiver_id": signal_data.receiver_id,
            "signal": signal_data.data
        })
        
        return {"status": "signal_sent"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{call_id}/participants", response_model=List[int])
async def get_call_participants(
    call_id: int,
    db: Session = Depends(get_db)
):
    """
    Get list of user IDs currently in a call without authentication.
    """
    call_service = CallService(db)
    try:
        # Skip user validation
        call_service.get_call(call_id, None)
        
        # Get active participants from the connection manager
        participants = connection_manager.get_call_participants(call_id)
        return participants
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
