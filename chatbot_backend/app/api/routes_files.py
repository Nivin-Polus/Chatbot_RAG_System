# app/api/routes_files.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from app.core.vector_singleton import get_vector_store
from app.core.database import get_db, DATABASE_AVAILABLE, InMemoryFileMetadata
from app.api.routes_auth import get_current_user
from app.utils.file_parser import parse_file
from app.services.file_storage import FileStorageService
from app.config import settings
from app.core.cache import get_cache
from app.services.activity_tracker import activity_tracker
from pydantic import BaseModel
import logging
from uuid import uuid4
import os

logger = logging.getLogger("files_logger")
logging.basicConfig(level=logging.INFO)

router = APIRouter()

# Initialize services
file_storage_service = FileStorageService()

# Response models
class FileMeta(BaseModel):
    file_id: str
    file_name: str
    uploaded_by: str
    upload_timestamp: str = None
    file_size: int = None
    processing_status: str = "completed"

# In-memory metadata store for MVP (replace with DB in production)
file_metadata_db = {}

# ------------------------
# Upload file endpoint
# ------------------------
@router.post("/upload", response_model=FileMeta)
async def upload_file(
    uploaded_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user has admin role
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can upload files")
    
    # Validate file type
    ext = uploaded_file.filename.split('.')[-1].lower()
    if ext not in settings.ALLOWED_FILE_TYPES.split(','):
        raise HTTPException(status_code=400, detail="File type not allowed")

    # Read file content
    content = await uploaded_file.read()
    text_chunks = parse_file(uploaded_file.filename, content)

    # Save file to disk using FileStorageService
    # Reset file position for reading again
    uploaded_file.file.seek(0)
    file_metadata = file_storage_service.save_file(uploaded_file, current_user["username"], db)
    file_id = file_metadata.file_id

    # Get singleton vector store and store embeddings
    vector_store = get_vector_store()
    logger.info(f"[UPLOAD DEBUG] Vector store type: {'Qdrant' if vector_store.client else 'In-memory fallback'}")
    logger.info(f"[UPLOAD DEBUG] Processing {len(text_chunks)} chunks for file: {uploaded_file.filename}")
    
    for i, chunk in enumerate(text_chunks):
        chunk_metadata = {
            "file_id": file_id,
            "file_name": uploaded_file.filename,
            "chunk_index": i,
            "text": chunk
        }
        vector_store.add_document(chunk, chunk_metadata)
        logger.info(f"[UPLOAD DEBUG] Added chunk {i+1}/{len(text_chunks)} to vector store")
    
    # Update processing status
    file_storage_service.update_processing_status(file_id, "completed", len(text_chunks), db)
    
    # Debug: Check if documents were actually stored
    if vector_store.client is None:
        logger.info(f"[UPLOAD DEBUG] Total documents in fallback storage: {len(vector_store.documents)}")
    else:
        logger.info(f"[UPLOAD DEBUG] Documents stored in Qdrant collection: {vector_store.collection_name}")

    # Store metadata in in-memory store for backward compatibility
    metadata = FileMeta(
        file_id=file_id,
        file_name=uploaded_file.filename,
        uploaded_by=current_user["username"],
        upload_timestamp=file_metadata.upload_timestamp.isoformat() if file_metadata.upload_timestamp else None,
        file_size=file_metadata.file_size,
        processing_status="completed"
    )
    file_metadata_db[file_id] = metadata

    logger.info(f"File uploaded: {uploaded_file.filename} by {current_user['username']}")

    # Log activity
    activity_tracker.log_activity(
        activity_type="file_upload",
        user=current_user["username"],
        details={
            "file_name": uploaded_file.filename,
            "file_id": file_id,
            "file_size": file_metadata.file_size,
            "file_type": ext,
            "chunk_count": len(text_chunks)
        },
        metadata={
            "processing_time": "completed",
            "vector_store_type": "qdrant" if vector_store.client else "in_memory"
        }
    )

    return metadata


# ------------------------
# Delete file endpoint
# ------------------------
@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user has admin role
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can delete files")
    
    # Check if file exists in both in-memory store and database
    if file_id not in file_metadata_db:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Remove all chunks for this file from vector store
        vector_store = get_vector_store()
        vector_store.delete_documents_by_file_id(file_id)

        # Delete file from disk and database using FileStorageService
        file_deleted = file_storage_service.delete_file(file_id, db)
        if not file_deleted:
            logger.warning(f"File {file_id} not found in database but exists in metadata store")

        # Remove metadata from in-memory store
        del file_metadata_db[file_id]

        # Invalidate cache (all cached answers containing this file)
        try:
            cache = get_cache()
            if cache and hasattr(cache, 'client') and cache.client:
                cache.client.flushdb()
                logger.info(f"Cache invalidated due to deletion of file {file_id}")
        except Exception as cache_error:
            logger.warning(f"Failed to invalidate cache: {cache_error}")

        logger.info(f"File deleted: {file_id} by {current_user['username']}")
        
        # Log activity
        activity_tracker.log_activity(
            activity_type="file_delete",
            user=current_user["username"],
            details={
                "file_id": file_id,
                "file_name": file_metadata_db.get(file_id, {}).get("file_name", "Unknown")
            }
        )
        
        return {"detail": f"File {file_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


# ------------------------
# List files endpoint
# ------------------------
@router.get("/list", response_model=List[FileMeta])
async def list_files(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        if DATABASE_AVAILABLE and db:
            # Get files from database
            from app.models.file_metadata import FileMetadata
            files = db.query(FileMetadata).all()
            
            # Convert to response format and update in-memory store
            file_list = []
            for file_metadata in files:
                file_dict = file_metadata.to_dict()
                metadata = FileMeta(
                    file_id=file_dict["file_id"],
                    file_name=file_dict["file_name"],
                    uploaded_by=file_dict["uploader_id"],
                    upload_timestamp=file_dict["upload_timestamp"],
                    file_size=file_dict["file_size"],
                    processing_status=file_dict["processing_status"]
                )
                file_list.append(metadata)
                # Keep in-memory store in sync
                file_metadata_db[file_dict["file_id"]] = metadata
            
            return file_list
        else:
            # Use in-memory storage only
            return list(file_metadata_db.values())
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        # Fallback to in-memory storage
        return list(file_metadata_db.values())


# ------------------------
# Download file endpoint
# ------------------------
@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download original file by file_id"""
    try:
        # Check permissions - admin can download any file, users can download their own
        file_path = file_storage_service.get_file_path(file_id, db)
        
        if not file_path:
            # Try in-memory metadata store as fallback
            if file_id in file_metadata_db:
                metadata = file_metadata_db[file_id]
                # Check permissions
                if current_user.get("role") != "admin" and metadata.uploaded_by != current_user["username"]:
                    raise HTTPException(status_code=403, detail="Permission denied")
                
                # Try to find file in uploads directory
                import glob
                possible_files = glob.glob(f"uploads/*/{file_id}.*")
                if possible_files:
                    file_path = possible_files[0]
                else:
                    raise HTTPException(status_code=404, detail="File not found on disk")
                    
                return FileResponse(
                    path=file_path,
                    filename=metadata.file_name,
                    media_type='application/octet-stream'
                )
            else:
                raise HTTPException(status_code=404, detail="File not found")
        
        # Database mode - get file metadata
        if DATABASE_AVAILABLE and db:
            from app.models.file_metadata import FileMetadata
            file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
            
            if not file_metadata:
                raise HTTPException(status_code=404, detail="File metadata not found")
            
            # Check if user has permission to download
            if current_user.get("role") != "admin" and file_metadata.uploader_id != current_user["username"]:
                raise HTTPException(status_code=403, detail="Permission denied")
            
            filename = file_metadata.file_name
        else:
            # Fallback mode - use in-memory metadata
            if file_id in file_metadata_db:
                metadata = file_metadata_db[file_id]
                if current_user.get("role") != "admin" and metadata.uploaded_by != current_user["username"]:
                    raise HTTPException(status_code=403, detail="Permission denied")
                filename = metadata.file_name
            else:
                raise HTTPException(status_code=404, detail="File metadata not found")
        
        # Check if file exists on disk
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        # Return file using FileResponse
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Download failed for file {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


# ------------------------
# Get file metadata endpoint
# ------------------------
@router.get("/metadata/{file_id}")
async def get_file_metadata(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get file metadata by file_id"""
    file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check permissions
    if current_user.get("role") != "admin" and file_metadata.uploader_id != current_user["username"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return file_metadata.to_dict()


# ------------------------
# Debug endpoint - Vector DB stats
# ------------------------
@router.get("/debug/vector-stats")
async def get_vector_stats(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to check vector database contents"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can access debug info")
    
    try:
        vector_store = get_vector_store()
        if vector_store.client:
            # Qdrant stats
            collection_info = vector_store.client.get_collection(vector_store.collection_name)
            count = vector_store.client.count(vector_store.collection_name)
            return {
                "vector_db_type": "qdrant",
                "collection_name": vector_store.collection_name,
                "total_documents": count.count,
                "collection_info": {
                    "status": collection_info.status,
                    "vectors_count": collection_info.vectors_count,
                    "points_count": collection_info.points_count
                }
            }
        else:
            # Fallback storage stats
            return {
                "vector_db_type": "in_memory_fallback",
                "total_documents": len(vector_store.documents),
                "document_ids": list(vector_store.documents.keys())
            }
    except Exception as e:
        return {"error": str(e), "vector_db_type": "unknown"}


# ------------------------
# Test endpoint for debugging
# ------------------------
@router.get("/test-reset")
async def test_reset_endpoint():
    """Test endpoint to verify routes are working"""
    return {"message": "Reset endpoint is accessible", "status": "working"}

@router.get("/debug-routes")
async def debug_routes():
    """Debug endpoint to list all available routes"""
    return {
        "available_routes": [
            "GET /files/list",
            "POST /files/upload", 
            "DELETE /files/{file_id}",
            "GET /files/download/{file_id}",
            "DELETE /files/reset-all",
            "GET /files/test-reset",
            "GET /files/debug-routes"
        ],
        "message": "Files routes are loaded"
    }

# ------------------------
# Reset all files (admin only)
# ------------------------
@router.delete("/reset-all")
async def reset_all_files(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset all files - delete all uploaded files and their data (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can reset files")
    
    try:
        import shutil
        import os
        from pathlib import Path
        
        # Get vector store instance
        vector_store = get_vector_store()
        
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
        
        # Clear in-memory metadata store
        file_metadata_db.clear()
        
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
            activity_type="system_reset",
            user=current_user["username"],
            details={
                "files_deleted": deleted_count,
                "vectors_cleaned": vector_cleanup_count,
                "reset_type": "complete_reset"
            }
        )
        
        logger.info(f"Reset completed: {deleted_count} files deleted, {vector_cleanup_count} vector entries cleaned by {current_user['username']}")
        
        return {
            "message": f"Successfully reset all files and vector data",
            "files_deleted": deleted_count,
            "vectors_cleaned": vector_cleanup_count,
            "reset_by": current_user["username"]
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to reset files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset files: {str(e)}")
