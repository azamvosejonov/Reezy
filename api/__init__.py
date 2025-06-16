"""
API package for the application.

This package contains all API endpoints organized by version.
"""
from fastapi import APIRouter

# Import versioned API routers
from .v1 import router as v1_router

# Create the main API router
router = APIRouter()

# Include versioned API routers
router.include_router(v1_router, prefix="")

__all__ = ['router', 'v1_router']
