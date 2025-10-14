# app/api/routes_files.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.vector_singleton import get_vector_store
from app.core.database import get_db
from app.api.routes_auth import get_current_user
from app.utils.file_parser import parse_file
from app.services.file_storage import FileStorageService
from app.models.file_metadata import FileMetadata
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
    uploader_id: Optional[str] = None
    upload_timestamp: Optional[str] = None
    file_size: Optional[int] = None
    processing_status: str = "completed"
    collection_id: Optional[str] = None

# In-memory metadata store for MVP (replace with DB in production)
file_metadata_db = {}

# ------------------------
# Upload file endpoint
# ------------------------
@router.post("/upload", response_model=List[FileMeta])
async def upload_file(
    files: Optional[List[UploadFile]] = File(None),
    uploaded_files: Optional[List[UploadFile]] = File(None, alias="uploaded_files"),
    single_file: Optional[UploadFile] = File(None, alias="file"),
    collection_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload one or multiple files"""
    
    logger.info(f"[UPLOAD DEBUG] Upload request from user: {current_user.get('username')}, role: {current_user.get('role')}")
    logger.info(f"[UPLOAD DEBUG] Collection ID: {collection_id}")
    
    # Check if user has appropriate role
    role = current_user.get("role")
    if role not in ["admin", "user_admin", "super_admin"]:
        logger.warning(f"[UPLOAD ERROR] Unauthorized upload attempt by user: {current_user.get('username')} with role: {role}")
        raise HTTPException(status_code=403, detail="Only admin users can upload files")

    # Normalize files from different input sources
    normalized_files: List[UploadFile] = []
    for file_group in (files, uploaded_files):
        if file_group:
            for candidate in file_group:
                if candidate and getattr(candidate, "filename", None):
                    normalized_files.append(candidate)
    if single_file and getattr(single_file, "filename", None):
        normalized_files.append(single_file)

    if not normalized_files:
        logger.warning(f"[UPLOAD ERROR] No files provided for upload by user: {current_user.get('username')}")
        raise HTTPException(status_code=400, detail="No files provided for upload")
    
    logger.info(f"[UPLOAD DEBUG] Processing {len(normalized_files)} files for upload")

    user_id = current_user.get("user_id")
    user_website_id = current_user.get("website_id")
    uploader_id = user_id or current_user.get("username")

    # Get website context if not available
    if role != "super_admin" and (not user_website_id or not user_id):
        from app.models.user import User
        user_obj = db.query(User).filter(User.username == current_user["username"]).first()
        if user_obj:
            if not user_website_id and user_obj.website_id:
                user_website_id = user_obj.website_id
            if not user_id and user_obj.user_id:
                user_id = user_obj.user_id
            if not uploader_id and user_obj.user_id:
                uploader_id = user_obj.user_id

    if not uploader_id:
        uploader_id = current_user["username"]

    # Allowed extensions
    allowed_extensions = {
        ext.strip().lower() for ext in settings.ALLOWED_FILE_TYPES.split(",") if ext.strip()
    }

    results: List[FileMeta] = []

    for uploaded_file in normalized_files:
        try:
            original_filename = uploaded_file.filename
            safe_filename = original_filename  # For now, use original filename
            logger.info(f"[UPLOAD DEBUG] Processing file: {original_filename}")
            
            # Validate file extension
            ext = safe_filename.split(".")[-1].lower() if "." in safe_filename else ""
            if ext not in allowed_extensions:
                raise HTTPException(status_code=400, detail=f"File type not allowed: {original_filename}")

            # Read file content
            content = await uploaded_file.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"Uploaded file is empty: {original_filename}")

            file_size = len(content)
            if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large: {original_filename}. Maximum size is {settings.MAX_FILE_SIZE_MB}MB"
                )

            # Parse file content
            try:
                text_chunks = parse_file(safe_filename, content)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse file {safe_filename}: {str(e)}")

            # Save file using FileStorageService
            file_metadata = file_storage_service.save_file_with_website(
                user_id=uploader_id,
                website_id=user_website_id,
                db=db,
                collection_id=collection_id,
                filename=safe_filename,
                file_content=content,
            )
            file_id = file_metadata.file_id

            # Get vector store and add documents
            vector_store = get_vector_store()
            for i, chunk in enumerate(text_chunks):
                chunk_metadata = {
                    "file_id": file_id,
                    "file_name": safe_filename,
                    "chunk_index": i,
                    "text": chunk,
                    "website_id": user_website_id,
                    "collection_id": collection_id,
                    "uploader_id": uploader_id
                }
                vector_store.add_document(chunk, chunk_metadata)

            # Update processing status
            file_storage_service.update_processing_status(file_id, "completed", len(text_chunks), db)

            # Create response metadata
            metadata = FileMeta(
                file_id=file_id,
                file_name=safe_filename,
                uploaded_by=current_user.get("username", "unknown"),
                uploader_id=uploader_id,
                upload_timestamp=file_metadata.upload_timestamp.isoformat() if file_metadata.upload_timestamp else None,
                file_size=file_metadata.file_size,
                processing_status="completed",
                collection_id=collection_id,
            )
            results.append(metadata)
            file_metadata_db[file_id] = metadata

            # Log activity
            activity_tracker.log_activity(
                activity_type="file_upload",
                user=current_user["username"],
                details={
                    "file_name": safe_filename,
                    "file_id": file_id,
                    "file_size": file_metadata.file_size,
                    "file_type": ext,
                    "chunk_count": len(text_chunks),
                    "collection_id": collection_id,
                },
                metadata={
                    "processing_time": "completed",
                    "vector_store_type": "qdrant" if vector_store.client else "in_memory",
                },
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[UPLOAD ERROR] Failed to upload {safe_filename}: {e}")
            raise HTTPException(status_code=500, detail=f"File upload failed for {safe_filename}: {str(e)}")

    logger.info(f"[UPLOAD SUCCESS] Successfully uploaded {len(results)} files for user: {current_user.get('username')}")
    return results


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
async def list_files(current_user: dict = Depends(get_current_user)):
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
    # Check permissions - admin can download any file, users can download their own
    file_path = file_storage_service.get_file_path(file_id, db)
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get file metadata to check permissions
    file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File metadata not found")
    
    # Check if user has permission to download
    if current_user.get("role") != "admin" and file_metadata.uploader_id != current_user["username"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Check if file exists on disk
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Return file using FileResponse (now that aiofiles is installed)
    return FileResponse(
        path=file_path,
        filename=file_metadata.file_name,
        media_type='application/octet-stream'
    )


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
