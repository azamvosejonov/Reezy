from fastapi import APIRouter
from api.v1.endpoints import blocks as blocks_endpoints

router = APIRouter()
router.include_router(blocks_endpoints.router, prefix="/api/v1/blocks", tags=["blocks"])
