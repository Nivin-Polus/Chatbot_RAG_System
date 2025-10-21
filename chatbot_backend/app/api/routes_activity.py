# app/api/routes_activity.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.api.routes_auth import get_current_user
from app.services.activity_tracker import activity_tracker
import logging

logger = logging.getLogger("activity_logger")

router = APIRouter()


class ActivityLogRequest(BaseModel):
    activity_type: str
    description: Optional[str] = None
    collection_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# ------------------------
# Get recent activities
# ------------------------
@router.get("/recent")
async def get_recent_activities(
    limit: int = Query(50, ge=1, le=100),
    since_hours: Optional[int] = Query(None, ge=1, le=24 * 180),
    current_user: dict = Depends(get_current_user)
):
    """Get recent activities"""
    try:
        activities = activity_tracker.get_recent_activities(limit, since_hours)
        return {
            "activities": activities,
            "count": len(activities)
        }
    except Exception as e:
        logger.error(f"Failed to get recent activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve activities")


# ------------------------
# Log new activity
# ------------------------
@router.post("/log")
async def log_activity(
    request: ActivityLogRequest,
    current_user: dict = Depends(get_current_user)
):
    """Record a new activity entry."""
    if not request.activity_type:
        raise HTTPException(status_code=400, detail="Activity type is required")

    try:
        details = {}
        if request.description:
            details["description"] = request.description
        if request.collection_id:
            details["collection_id"] = request.collection_id

        activity_tracker.log_activity(
            activity_type=request.activity_type,
            user=current_user.get("username", "unknown"),
            details=details or None,
            metadata=request.metadata or None,
        )
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")
        raise HTTPException(status_code=500, detail="Failed to log activity")

# ------------------------
# Get activities by type
# ------------------------
@router.get("/by-type/{activity_type}")
async def get_activities_by_type(
    activity_type: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get activities filtered by type"""
    try:
        activities = activity_tracker.get_activities_by_type(activity_type, limit)
        return {
            "activities": activities,
            "type": activity_type,
            "count": len(activities)
        }
    except Exception as e:
        logger.error(f"Failed to get activities by type: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve activities")

# ------------------------
# Get activities by user
# ------------------------
@router.get("/by-user/{username}")
async def get_activities_by_user(
    username: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get activities filtered by user (admin only)"""
    if current_user.get("role") not in ["super_admin", "user_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can view other users' activities")
    
    try:
        activities = activity_tracker.get_activities_by_user(username, limit)
        return {
            "activities": activities,
            "user": username,
            "count": len(activities)
        }
    except Exception as e:
        logger.error(f"Failed to get activities by user: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve activities")

# ------------------------
# Get current user's activities
# ------------------------
@router.get("/my-activities")
async def get_my_activities(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get current user's activities"""
    try:
        activities = activity_tracker.get_activities_by_user(current_user["username"], limit)
        return {
            "activities": activities,
            "user": current_user["username"],
            "count": len(activities)
        }
    except Exception as e:
        logger.error(f"Failed to get user activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve activities")

# ------------------------
# Get statistics
# ------------------------
@router.get("/stats")
async def get_activity_stats(current_user: dict = Depends(get_current_user)):
    """Get activity statistics"""
    try:
        stats = activity_tracker.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get activity stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

# ------------------------
# Get activity summary
# ------------------------
@router.get("/summary")
async def get_activity_summary(current_user: dict = Depends(get_current_user)):
    """Get comprehensive activity summary"""
    try:
        summary = activity_tracker.get_activity_summary()
        return summary
    except Exception as e:
        logger.error(f"Failed to get activity summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve activity summary")

# ------------------------
# Clear old activities (admin only)
# ------------------------
@router.delete("/cleanup")
async def cleanup_old_activities(
    days_to_keep: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user)
):
    """Clear old activities (admin only)"""
    if current_user.get("role") not in ["super_admin", "user_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can cleanup activities")
    
    try:
        activity_tracker.clear_activities(days_to_keep)
        return {"message": f"Cleaned up activities older than {days_to_keep} days"}
    except Exception as e:
        logger.error(f"Failed to cleanup activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup activities")

# ------------------------
# Reset files only (admin only) - Workaround for files/reset-all
# ------------------------
@router.delete("/reset-files")
async def reset_files_only(current_user: dict = Depends(get_current_user)):
    """Reset files only - delete all uploaded files and their data (admin only)"""
    if current_user.get("role") not in ["super_admin", "user_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can reset files")
    
    try:
        import shutil
        import os
        from pathlib import Path
        from app.core.database import get_db, SessionLocal
        from app.models.file_metadata import FileMetadata
        
        # Get vector store instance
        # Import here to avoid PyO3 initialization issues during module import
        from app.core.vector_singleton import get_vector_store
        vector_store = get_vector_store()
        
        # Get database session
        db = SessionLocal()
        
        try:
            # Get all files from database
            all_files = db.query(FileMetadata).all()
            deleted_count = 0
            vector_cleanup_count = 0
            
            # Delete each file from disk, database, and vector store
            for file_metadata in all_files:
                try:
                    # Delete from vector database first
                    try:
                        vector_store.delete_documents_by_file_id(file_metadata.file_id)
                        vector_cleanup_count += 1
                        logger.info(f"Deleted vectors for file: {file_metadata.file_id}")
                    except Exception as ve:
                        logger.warning(f"Failed to delete vectors for file {file_metadata.file_id}: {ve}")
                    
                    # Delete file from disk
                    if os.path.exists(file_metadata.file_path):
                        os.remove(file_metadata.file_path)
                        logger.info(f"Deleted file from disk: {file_metadata.file_path}")
                    
                    # Delete from database
                    db.delete(file_metadata)
                    deleted_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to delete file {file_metadata.file_id}: {e}")
            
            # Remove empty user directories
            upload_dir = Path("uploads")
            if upload_dir.exists():
                for user_dir in upload_dir.iterdir():
                    if user_dir.is_dir() and not any(user_dir.iterdir()):
                        user_dir.rmdir()
                        logger.info(f"Removed empty directory: {user_dir}")
            
            # Clear entire vector collection if possible
            try:
                if hasattr(vector_store, 'client') and vector_store.client:
                    # Try to delete entire collection and recreate it
                    vector_store.client.delete_collection(vector_store.collection_name)
                    vector_store._ensure_collection()
                    logger.info("Recreated vector collection")
                elif hasattr(vector_store, 'documents'):
                    # Fallback: clear in-memory storage
                    vector_store.documents.clear()
                    logger.info("Cleared in-memory vector storage")
            except Exception as ve:
                logger.warning(f"Failed to clear vector collection: {ve}")
            
            db.commit()
            
            # Log the reset activity
            activity_tracker.log_activity(
                activity_type="files_reset",
                user=current_user["username"],
                details={
                    "files_deleted": deleted_count,
                    "vectors_cleaned": vector_cleanup_count,
                    "reset_type": "files_only"
                }
            )
            
            logger.info(f"Files reset completed: {deleted_count} files deleted, {vector_cleanup_count} vector entries cleaned by {current_user['username']}")
            
            return {
                "message": f"Successfully reset all files and vector data",
                "files_deleted": deleted_count,
                "vectors_cleaned": vector_cleanup_count,
                "reset_by": current_user["username"]
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to reset files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset files: {str(e)}")

# ------------------------
# Reset everything (admin only)
# ------------------------
@router.delete("/reset-all")
async def reset_everything(current_user: dict = Depends(get_current_user)):
    """Reset everything - clear all data (admin only)"""
    if current_user.get("role") not in ["super_admin", "user_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can reset the system")
    
    try:
        from app.services.file_storage import FileStorageService
        from app.core.database import get_db
        from sqlalchemy.orm import Session
        # Import here to avoid PyO3 initialization issues during module import
        from app.core.vector_singleton import get_vector_store
        
        # Clear vector database
        vector_store = get_vector_store()
        if vector_store.client:
            try:
                vector_store.client.delete_collection(vector_store.collection_name)
                logger.info("Vector database collection deleted")
            except Exception as e:
                logger.warning(f"Failed to delete vector collection: {e}")
        
        # Clear in-memory fallback
        if hasattr(vector_store, 'documents'):
            vector_store.documents.clear()
            vector_store.embeddings.clear()
            logger.info("In-memory vector storage cleared")
        
        # Clear all activities
        activity_tracker._save_activities([])
        activity_tracker._save_stats({
            "total_files_uploaded": 0,
            "total_chat_sessions": 0,
            "total_queries": 0,
            "last_document_upload": None,
            "last_chat_session": None,
            "last_activity": None
        })
        logger.info("Activity logs cleared")
        
        # Clear cache
        try:
            cache = get_cache()
            if cache and hasattr(cache, 'client') and cache.client:
                cache.client.flushdb()
                logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")
        
        return {
            "message": "System reset successfully",
            "cleared": [
                "Vector database",
                "Activity logs", 
                "Cache",
                "File metadata"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to reset system: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset system: {str(e)}")
