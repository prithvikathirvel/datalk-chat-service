from fastapi import APIRouter, Depends 
from app.core.config import config
from app.api.v1.chat import chat_router

router = APIRouter(tags=["v1"])

router.include_router(chat_router)


@router.get("/health", summary="Health Check", description="Check the health of the API")
async def health_check():
    return {"status": "ok", "version": config.VERSION_PREFIX}