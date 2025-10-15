# app/api/routes_files.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.vector_singleton import get_vector_store
from app.core.database import get_db
from app.api.routes_auth import get_current_user
from app.utils.file_parser import parse_file
from app.utils.file_sanitizer import (
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
)
from app.services.file_storage import FileStorageService
from app.models.file_metadata import FileMetadata
from app.models.user import User
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

    # Check permissions
    role = current_user.get("role")
    if role not in ["admin", "user_admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can upload files")

    # Normalize files
    normalized_files: List[UploadFile] = []
    for file_group in (files, uploaded_files):
        if file_group:
            for candidate in file_group:
                if candidate and getattr(candidate, "filename", None):
                    normalized_files.append(candidate)
    if single_file and getattr(single_file, "filename", None):
        normalized_files.append(single_file)

    if not normalized_files:
        raise HTTPException(status_code=400, detail="No files provided for upload")

    user_id = current_user.get("user_id")
    website_id = current_user.get("website_id")
    uploader_id = user_id or current_user.get("username")

    # Allowed file extensions
    allowed_extensions = {
        ext.strip().lower() for ext in settings.ALLOWED_FILE_TYPES.split(",") if ext.strip()
    }

    results: List[FileMeta] = []

    for uploaded_file in normalized_files:
        try:
            original_filename = uploaded_file.filename
            safe_filename = sanitize_filename(original_filename)
            ext = safe_filename.split(".")[-1].lower() if "." in safe_filename else ""

            # Validate file type & size
            if not validate_file_extension(safe_filename, allowed_extensions):
                raise HTTPException(status_code=400, detail=f"File type not allowed: {original_filename}")

            content = await uploaded_file.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"Uploaded file is empty: {original_filename}")

            if not validate_file_size(len(content), settings.MAX_FILE_SIZE_MB):
                raise HTTPException(status_code=400, detail=f"File too large: {original_filename}")

            # Parse text chunks for embedding
            text_chunks = parse_file(safe_filename, content)

            # --- Save file using safe keyword-only approach ---
            file_params = {
                "user_id": uploader_id,
                "website_id": website_id,
                "db": db,
                "collection_id": collection_id,
                "filename": safe_filename,
                "file_content": content,
            }
            logger.info(f"[SAVE FILE] Parameters: {file_params}")

            file_metadata = file_storage_service.save_file_with_website(**file_params)

            file_id = file_metadata.file_id
            vector_store = get_vector_store()

            for i, chunk in enumerate(text_chunks):
                metadata = {
                    "file_id": file_id,
                    "file_name": safe_filename,
                    "chunk_index": i,
                    "text": chunk,
                    "website_id": website_id,
                    "collection_id": collection_id,
                    "uploader_id": uploader_id
                }
                vector_store.add_document(chunk, metadata)

            file_storage_service.update_processing_status(file_id, "completed", len(text_chunks), db)

            meta = FileMeta(
                file_id=file_id,
                file_name=safe_filename,
                uploaded_by=current_user.get("username", "unknown"),
                uploader_id=uploader_id,
                upload_timestamp=file_metadata.upload_timestamp.isoformat() if file_metadata.upload_timestamp else None,
                file_size=file_metadata.file_size,
                processing_status="completed",
                collection_id=collection_id,
            )

            results.append(meta)
            file_metadata_db[file_id] = meta

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
            )

        except Exception as e:
            logger.error(f"[UPLOAD ERROR] Failed to upload {safe_filename}: {e}")
            raise HTTPException(status_code=500, detail=f"File upload failed for {safe_filename}: {str(e)}")

    logger.info(f"[UPLOAD SUCCESS] Uploaded {len(results)} files by {current_user.get('username')}")
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
    if current_user.get("role") not in {"admin", "user_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only admin users can delete files")

    file_record = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Remove all chunks for this file from vector store
        vector_store = get_vector_store()
        vector_store.delete_documents_by_file_id(file_id)

        # Delete file from disk and database using FileStorageService
        file_deleted = file_storage_service.delete_file(file_id, db)
        if not file_deleted:
            logger.warning(f"File {file_id} not found in database during deletion")

        # Remove metadata from in-memory store if present
        file_metadata_db.pop(file_id, None)

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
                "file_name": file_record.file_name,
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
async def list_files(
    collection_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    role = current_user.get("role")
    user_id = current_user.get("user_id")
    website_id = current_user.get("website_id")

    if (not user_id or not website_id) and current_user.get("username"):
        user_record = db.query(User).filter(User.username == current_user["username"]).first()
        if user_record:
            user_id = user_id or user_record.user_id
            website_id = website_id or user_record.website_id

    query = db.query(FileMetadata)

    if collection_id:
        query = query.filter(FileMetadata.collection_id == collection_id)

    if role != "super_admin":
        if website_id:
            query = query.filter(FileMetadata.website_id == website_id)
        elif user_id:
            query = query.filter(FileMetadata.uploader_id == user_id)

    files = query.order_by(FileMetadata.upload_timestamp.desc()).all()

    response_items: List[FileMeta] = []
    for record in files:
        uploader_username = record.uploader.username if record.uploader else record.uploader_id
        item = FileMeta(
            file_id=record.file_id,
            file_name=record.file_name,
            uploaded_by=uploader_username,
            uploader_id=record.uploader_id,
            upload_timestamp=record.upload_timestamp.isoformat() if record.upload_timestamp else None,
            file_size=record.file_size,
            processing_status=record.processing_status,
            collection_id=record.collection_id,
        )
        response_items.append(item)
        file_metadata_db[record.file_id] = item

    return response_items


# ------------------------
# Download file endpoint
# ------------------------
@router.get("/download/{identifier}")
async def download_file(
    identifier: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download original file by file_id or file_name"""
    from app.models.user import User

    # Try to find by file_id first
    file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == identifier).first()

    # If not found, try by file_name
    if not file_metadata:
        file_metadata = db.query(FileMetadata).filter(FileMetadata.file_name == identifier).first()

    if not file_metadata:
        raise HTTPException(status_code=404, detail="File metadata not found")

    # --- Permission check ---
    role = current_user.get("role")
    current_user_id = current_user.get("user_id")
    current_user_website = current_user.get("website_id")

    # Load user info if missing
    if (not current_user_id or not current_user_website) and current_user.get("username"):
        user_record = db.query(User).filter(User.username == current_user["username"]).first()
        if user_record:
            current_user_id = current_user_id or user_record.user_id
            current_user_website = current_user_website or user_record.website_id

    # Restrict access to files of other websites (except super_admin)
    if (
        role != "super_admin"
        and file_metadata.website_id
        and current_user_website
        and file_metadata.website_id != current_user_website
    ):
        raise HTTPException(status_code=403, detail="File belongs to a different website")

    # Restrict user access to only their own uploads (if not admin)
    if role not in {"admin", "user_admin", "super_admin"}:
        if not current_user_id or file_metadata.uploader_id != current_user_id:
            raise HTTPException(status_code=403, detail="Permission denied")

    # --- Fetch file binary ---
    file_storage_service = FileStorageService()
    binary_record = file_storage_service.get_file_binary(file_metadata.file_id, db)

    if not binary_record or not binary_record.data:
        raise HTTPException(status_code=404, detail="File data not found")

    filename = file_metadata.file_name or f"download-{file_metadata.file_id}"
    media_type = (
        binary_record.mime_type
        or file_metadata.file_type
        or "application/octet-stream"
    )

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }

    return StreamingResponse(iter([binary_record.data]), media_type=media_type, headers=headers)


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
    
    role = current_user.get("role")
    current_user_id = current_user.get("user_id")
    current_user_website = current_user.get("website_id")

    if (not current_user_id or not current_user_website) and current_user.get("username"):
        user_record = db.query(User).filter(User.username == current_user["username"]).first()
        if user_record:
            current_user_id = current_user_id or user_record.user_id
            current_user_website = current_user_website or user_record.website_id

    if role != "super_admin" and file_metadata.website_id and current_user_website and file_metadata.website_id != current_user_website:
        raise HTTPException(status_code=403, detail="File belongs to a different website")

    if role not in {"admin", "user_admin", "super_admin"}:
        if not current_user_id or file_metadata.uploader_id != current_user_id:
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
