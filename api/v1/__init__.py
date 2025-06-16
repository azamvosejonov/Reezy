"""
API v1 package.

This package contains all API endpoints for version 1 of the API.
"""
from fastapi import APIRouter
from .endpoints import router as endpoints_router
from .endpoints.advertisement_approval import router as approval_router

# Create the main API v1 router
router = APIRouter()

# Include all endpoints
router.include_router(endpoints_router, prefix="")
router.include_router(approval_router, prefix="/advertisements", tags=["advertisement-approval"])

__all__ = ['router']
