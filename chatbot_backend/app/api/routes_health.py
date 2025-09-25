from fastapi import APIRouter, Depends, HTTPException
from app.api.routes_auth import get_current_user
from app.services.health_monitor import HealthMonitorService
from app.services.file_storage import FileStorageService
from app.services.chat_tracking import ChatTrackingService
from app.core.database import get_db
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Initialize services
health_service = HealthMonitorService()
file_service = FileStorageService()
chat_service = ChatTrackingService()


@router.get("/health")
async def system_health():
    """Public health check endpoint"""
    try:
        overview = health_service.get_system_overview()
        return overview
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "overall_status": "unhealthy",
            "error": str(e)
        }


@router.get("/health/detailed")
async def detailed_health_check(current_user: dict = Depends(get_current_user)):
    """Detailed health check (authenticated users only)"""
    try:
        overview = health_service.get_system_overview()
        return overview
    except Exception as e:
        logger.error(f"Detailed health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/qdrant")
async def qdrant_health(current_user: dict = Depends(get_current_user)):
    """Check Qdrant vector database health"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return health_service.check_qdrant_health()


@router.get("/health/ai")
async def ai_model_health(current_user: dict = Depends(get_current_user)):
    """Check AI model health"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return health_service.check_ai_model_health()


@router.get("/health/files")
async def file_processing_health(current_user: dict = Depends(get_current_user)):
    """Check file processing health"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return health_service.check_file_processing_health()


@router.get("/health/auth")
async def authentication_health(current_user: dict = Depends(get_current_user)):
    """Check authentication system health"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return health_service.check_authentication_health()


@router.get("/stats/storage")
async def storage_statistics(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get storage statistics"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return file_service.get_storage_stats(db)


@router.get("/stats/chat")
async def chat_statistics(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get chat statistics"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return chat_service.get_chat_analytics(db)


@router.get("/stats/overview")
async def system_overview(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get complete system overview with stats"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Get all statistics
        health_overview = health_service.get_system_overview()
        storage_stats = file_service.get_storage_stats(db)
        chat_stats = chat_service.get_chat_analytics(db)
        
        return {
            "system_health": health_overview,
            "storage_statistics": storage_stats,
            "chat_analytics": chat_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get system overview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get system overview: {str(e)}")
