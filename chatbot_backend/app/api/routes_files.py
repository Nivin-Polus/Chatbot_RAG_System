# app/api/routes_files.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form, Request, status, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db, DATABASE_AVAILABLE
from app.api.routes_auth import get_current_user
from app.models.file_metadata import FileMetadata
from app.utils.file_parser import parse_file
from app.services.file_storage import FileStorageService
from app.config import settings
from app.core.cache import get_cache
from app.services.activity_tracker import activity_tracker
from pydantic import BaseModel
import logging
from uuid import uuid4
from app.utils.file_sanitizer import sanitize_filename, validate_file_extension, validate_file_size

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

@router.post("/upload")
async def upload_file(
    files: Optional[List[UploadFile]] = File(None),
    uploaded_files: Optional[List[UploadFile]] = File(None, alias="uploaded_files"),
    single_file: Optional[UploadFile] = File(None, alias="file"),
    collection_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload one or multiple files"""

    role = current_user.get("role")
    if role not in ["admin", "user_admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can upload files")

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
    user_website_id = current_user.get("website_id")
    uploader_id = user_id or current_user.get("username")

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

    collection_obj = None
    if collection_id:
        from app.models.collection import Collection, CollectionUser

        collection_obj = db.query(Collection).filter(Collection.collection_id == collection_id).first()
        if not collection_obj:
            raise HTTPException(status_code=404, detail="Collection not found")

        if not user_website_id and collection_obj.website_id:
            user_website_id = collection_obj.website_id

        if (
            collection_obj.website_id
            and user_website_id
            and collection_obj.website_id != user_website_id
            and role != "super_admin"
        ):
            raise HTTPException(status_code=403, detail="Collection does not belong to your website")

        if role in ["user_admin", "admin"]:
            if not user_id or collection_obj.admin_user_id != user_id:
                raise HTTPException(status_code=403, detail="You do not manage this collection")
        elif role == "user":
            membership = db.query(CollectionUser).filter(
                CollectionUser.collection_id == collection_id,
                CollectionUser.user_id == user_id,
            ).first()
            if not membership:
                raise HTTPException(status_code=403, detail="You do not have access to this collection")

    if not uploader_id:
        uploader_id = current_user["username"]

    if not user_website_id:
        logger.info(f"Allowing file upload without website context for user: {current_user['username']}")

    results: List[FileMeta] = []

    # Allowed extensions
    allowed_extensions = {
        ext.strip().lower() for ext in settings.ALLOWED_FILE_TYPES.split(",") if ext.strip()
    }

    for uploaded_file in normalized_files:
        original_filename = uploaded_file.filename
        safe_filename = sanitize_filename(original_filename)
        ext = safe_filename.split(".")[-1].lower() if "." in safe_filename else ""

        if not validate_file_extension(safe_filename, allowed_extensions):
            raise HTTPException(status_code=400, detail=f"File type not allowed: {original_filename}")

        try:
            content = await uploaded_file.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"Uploaded file is empty: {original_filename}")

            file_size = len(content)
            if not validate_file_size(file_size, settings.MAX_FILE_SIZE_MB):
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large: {original_filename}. Maximum size is {settings.MAX_FILE_SIZE_MB}MB"
                )

            try:
                text_chunks = parse_file(safe_filename, content)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse file {safe_filename}: {str(e)}")

            file_metadata = file_storage_service.save_file_with_website(
                user_id=uploader_id,
                website_id=user_website_id,
                db=db,
                collection_id=collection_id,
                filename=safe_filename,
                file_content=content,
            )
            file_id = file_metadata.file_id

            from app.core.vector_singleton import get_vector_store
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

            file_storage_service.update_processing_status(file_id, "completed", len(text_chunks), db)

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
    if current_user.get("role") not in ["admin", "user_admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can delete files")
    
    # Check if file exists in both in-memory store and database
    if file_id not in file_metadata_db:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Remove all chunks for this file from vector store
        # Import here to avoid PyO3 initialization issues during module import
        from app.core.vector_singleton import get_vector_store
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
async def list_files(
    collection_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if DATABASE_AVAILABLE and db:
            # Get files from database
            from app.models.file_metadata import FileMetadata
            from app.models.user import User
            from app.models.collection import Collection, CollectionUser

            query = db.query(FileMetadata)

            if collection_id:
                query = query.filter(FileMetadata.collection_id == collection_id)

            role = current_user.get("role")
            user_id = current_user.get("user_id")
            user_website_id = current_user.get("website_id")

            if role != "super_admin":
                if not user_website_id and user_id:
                    user_obj = db.query(User).filter(User.user_id == user_id).first()
                    user_website_id = user_obj.website_id if user_obj else None

                if user_website_id:
                    query = query.filter(FileMetadata.website_id == user_website_id)
                elif user_id:
                    query = query.filter(FileMetadata.uploader_id == user_id)

                if collection_id:
                    if role in ["user_admin", "admin"]:
                        collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
                        if not collection or collection.admin_user_id != user_id:
                            raise HTTPException(status_code=403, detail="You do not manage this collection")
                    elif role == "user":
                        membership = db.query(CollectionUser).filter(
                            CollectionUser.collection_id == collection_id,
                            CollectionUser.user_id == user_id
                        ).first()
                        if not membership:
                            raise HTTPException(status_code=403, detail="You do not have access to this collection")

            files = query.all()

            # Convert to response format and update in-memory store
            file_list = []
            for file_metadata in files:
                file_dict = file_metadata.to_dict()
                uploader_name = (
                    file_metadata.uploader.username
                    if hasattr(file_metadata, "uploader") and file_metadata.uploader
                    else file_dict.get("uploader_id")
                )
                metadata = FileMeta(
                    file_id=file_dict["file_id"],
                    file_name=file_dict["file_name"],
                    uploaded_by=uploader_name,
                    uploader_id=file_dict.get("uploader_id"),
                    upload_timestamp=file_dict["upload_timestamp"],
                    file_size=file_dict["file_size"],
                    processing_status=file_dict["processing_status"],
                    collection_id=file_dict.get("collection_id")
                )
                file_list.append(metadata)
                # Keep in-memory store in sync
                file_metadata_db[file_dict["file_id"]] = metadata
            
            return file_list
        else:
            # Use in-memory storage only
            if collection_id:
                return [meta for meta in file_metadata_db.values() if meta.collection_id == collection_id]
            return list(file_metadata_db.values())
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        # Fallback to in-memory storage
        if collection_id:
            return [meta for meta in file_metadata_db.values() if meta.collection_id == collection_id]
        return list(file_metadata_db.values())


# ------------------------
# Download file endpoint
# ------------------------
@router.get("/download/by-name/{collection_id}/{file_name}")
async def download_file_by_name(
    collection_id: str,
    file_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download original file by collection and file name."""
    from app.models.file_metadata import FileMetadata

    file_record = (
        db.query(FileMetadata)
        .filter(
            FileMetadata.collection_id == collection_id,
            FileMetadata.file_name == file_name,
        )
        .first()
    )

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    return await download_file(
        file_id=file_record.file_id,
        current_user=current_user,
        db=db,
    )


@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download original file by file_id"""
    try:
        role = current_user.get("role")
        user_id = current_user.get("user_id")
        user_website_id = current_user.get("website_id")

        requested_identifier = file_id
        resolved_file_id = file_id

        db_metadata = None
        if DATABASE_AVAILABLE and db:
            from app.models.file_metadata import FileMetadata
            db_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()

        cached_metadata = file_metadata_db.get(file_id)

        if not db_metadata and not cached_metadata:
            fallback_db_metadata = None
            fallback_cached_metadata = None

            if DATABASE_AVAILABLE and db:
                fallback_db_metadata = (
                    db.query(FileMetadata)
                    .filter(FileMetadata.file_name == requested_identifier)
                    .order_by(FileMetadata.upload_timestamp.desc())
                    .first()
                )

            if not fallback_db_metadata:
                fallback_cached_metadata = next(
                    (meta for meta in file_metadata_db.values() if meta.file_name == requested_identifier),
                    None,
                )

            if fallback_db_metadata:
                db_metadata = fallback_db_metadata
                resolved_file_id = fallback_db_metadata.file_id
            elif fallback_cached_metadata:
                cached_metadata = fallback_cached_metadata
                resolved_file_id = fallback_cached_metadata.file_id
            else:
                raise HTTPException(status_code=404, detail="File metadata not found")

        if db_metadata is None and DATABASE_AVAILABLE and db and resolved_file_id != requested_identifier:
            from app.models.file_metadata import FileMetadata
            db_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == resolved_file_id).first()

        file_id = resolved_file_id

        filename = None
        uploader_id = None
        collection_id = None
        website_id = None

        if db_metadata:
            filename = db_metadata.file_name
            uploader_id = db_metadata.uploader_id
            collection_id = db_metadata.collection_id
            website_id = db_metadata.website_id
        if cached_metadata:
            filename = filename or cached_metadata.file_name
            uploader_id = uploader_id or cached_metadata.uploader_id
            collection_id = collection_id or cached_metadata.collection_id

        if role != "super_admin":
            if website_id and user_website_id and website_id != user_website_id:
                raise HTTPException(status_code=403, detail="File belongs to a different website")

            if uploader_id and uploader_id == user_id:
                pass  # uploader can always download
            else:
                if collection_id and db_metadata:
                    from app.models.collection import Collection, CollectionUser

                    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
                    if role in ["user_admin", "admin"]:
                        if not collection or collection.admin_user_id != user_id:
                            raise HTTPException(status_code=403, detail="You do not manage this collection")
                    elif role == "user":
                        membership = db.query(CollectionUser).filter(
                            CollectionUser.collection_id == collection_id,
                            CollectionUser.user_id == user_id,
                        ).first()
                        if not membership:
                            raise HTTPException(status_code=403, detail="You do not have access to this collection")
                elif collection_id and not db_metadata:
                    raise HTTPException(status_code=403, detail="Unable to verify collection permissions")
                elif role == "user":
                    raise HTTPException(status_code=403, detail="Permission denied")

        binary_record = file_storage_service.get_file_binary(file_id, db)
        if not binary_record or not binary_record.data:
            raise HTTPException(status_code=404, detail="File data not found")

        if not filename:
            filename = f"download-{file_id}"

        if db_metadata and not filename:
            filename = db_metadata.file_name

        media_type = binary_record.mime_type
        if not media_type and db_metadata:
            media_type = db_metadata.file_type
        if not media_type:
            media_type = "application/octet-stream"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }

        async def iter_file():
            yield binary_record.data

        return StreamingResponse(iter_file(), media_type=media_type, headers=headers)

    except HTTPException:
        raise
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
    if current_user.get("role") not in ["admin", "user_admin", "super_admin"] and file_metadata.uploader_id != current_user["username"]:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    return file_metadata.to_dict()


# ------------------------
# Debug endpoint - Vector DB stats
# ------------------------
@router.get("/debug/vector-stats")
async def get_vector_stats(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to check vector database contents"""
    if current_user.get("role") not in ["admin", "user_admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can access debug info")
    
    try:
        # Import here to avoid PyO3 initialization issues during module import
        from app.core.vector_singleton import get_vector_store
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
    if current_user.get("role") not in ["admin", "user_admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can reset files")
    
    try:
        import shutil
        import os
        from pathlib import Path
        
        # Get vector store instance
        # Import here to avoid PyO3 initialization issues during module import
        from app.core.vector_singleton import get_vector_store
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
