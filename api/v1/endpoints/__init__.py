"""
API v1 endpoints package.

This package contains all endpoint modules for version 1 of the API.
"""
from fastapi import APIRouter
from main import AuthRouter
from routers import posts

# Import all endpoint routers
from . import advertisements
from . import blocks
from . import users

# Create a router for all v1 endpoints
router = AuthRouter()

# Include all endpoint routers
# Note: Routers already have their own prefixes
router.include_router(posts.router)
router.include_router(advertisements.router)
router.include_router(blocks.router)
router.include_router(users.router)

__all__ = [
    'router',
    'posts',
    'advertisements',
    'blocks',
    'users',
    'AuthRouter'
]
