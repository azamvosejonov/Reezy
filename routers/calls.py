from fastapi import APIRouter
from api.endpoints import calls

# Create a router for calls
router = APIRouter()

# Include the calls endpoints
router.include_router(
    calls.router,
    prefix="/calls",
    tags=["calls"]
)
