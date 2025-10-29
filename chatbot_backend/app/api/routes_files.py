# app/api/routes_files.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from collections.abc import Sequence
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
from app.models.collection import Collection
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
    uploaded_files: Optional[Union[UploadFile, List[UploadFile]]] = File(None, alias="uploaded_files"),
    single_file: Optional[UploadFile] = File(None, alias="file"),
    collection_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload one or multiple files"""
    logger.info(f"[UPLOAD DEBUG] Upload request from user: {current_user.get('username')}, role: {current_user.get('role')}")
    
    # Debug: Log what files we received
    logger.info(f"[UPLOAD DEBUG] Received files: {files is not None}")
    logger.info(f"[UPLOAD DEBUG] Received uploaded_files: {uploaded_files is not None}")
    logger.info(f"[UPLOAD DEBUG] Received single_file: {single_file is not None}")
    logger.info(f"[UPLOAD DEBUG] Received collection_id: {collection_id}")
    
    # Additional debug info for uploaded_files
    if uploaded_files:
        if isinstance(uploaded_files, list):
            logger.info(f"[UPLOAD DEBUG] uploaded_files is a list with {len(uploaded_files)} items")
            for i, uf in enumerate(uploaded_files):
                logger.info(f"[UPLOAD DEBUG] uploaded_files[{i}].filename: {getattr(uf, 'filename', 'None')}")
        else:
            logger.info(f"[UPLOAD DEBUG] uploaded_files is a single file: {getattr(uploaded_files, 'filename', 'None')}")

    # Check permissions
    role = current_user.get("role")
    if role not in ["user_admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can upload files")

    # Normalize files
    normalized_files: List[UploadFile] = []

    def _add_candidates(group):
        logger.info(f"[UPLOAD DEBUG] _add_candidates called with group: {type(group)}")
        if not group:
            logger.info("[UPLOAD DEBUG] _add_candidates: group is falsy, returning")
            return
        logger.info(f"[UPLOAD DEBUG] _add_candidates: group is not falsy")
        
        if isinstance(group, Sequence) and not isinstance(group, (str, bytes)):
            items = list(group)
            logger.info(f"[UPLOAD DEBUG] _add_candidates: group is Sequence, items count: {len(items)}")
        else:
            items = [group]
            logger.info(f"[UPLOAD DEBUG] _add_candidates: group is not Sequence, items count: {len(items)}")
            
        for i, candidate in enumerate(items):
            logger.info(f"[UPLOAD DEBUG] _add_candidates: checking candidate {i}: {type(candidate)}")
            if candidate:
                logger.info(f"[UPLOAD DEBUG] _add_candidates: candidate {i} is truthy")
                # Accept Starlette/FastAPI UploadFile or any object with file-like API
                has_required_attrs = hasattr(candidate, "filename") and hasattr(candidate, "read")
                if has_required_attrs:
                    filename = getattr(candidate, "filename", None)
                    logger.info(f"[UPLOAD DEBUG] _add_candidates: candidate {i} filename: {filename}")
                    if filename:
                        normalized_files.append(candidate)
                        logger.info(f"[UPLOAD DEBUG] Added file: {filename}")
                    else:
                        logger.info(f"[UPLOAD DEBUG] _add_candidates: candidate {i} missing filename")
                else:
                    logger.info(f"[UPLOAD DEBUG] _add_candidates: candidate {i} missing required attrs (filename/read)")
            else:
                logger.info(f"[UPLOAD DEBUG] _add_candidates: candidate {i} is falsy")

    _add_candidates(files)
    _add_candidates(uploaded_files)
    if single_file and getattr(single_file, "filename", None):
        normalized_files.append(single_file)
        logger.info(f"[UPLOAD DEBUG] Added single file: {single_file.filename}")

    logger.info(f"[UPLOAD DEBUG] Total normalized files: {len(normalized_files)}")
    
    if not normalized_files:
        logger.error("[UPLOAD ERROR] No files provided for upload - files list is empty")
        raise HTTPException(status_code=400, detail="No files provided for upload")

    # Get user from database using username (most reliable)
    username = current_user.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Username not found in token")
    
    user_record = db.query(User).filter(User.username == username).first()
    if not user_record:
        raise HTTPException(status_code=403, detail=f"User '{username}' not found in database")
    
    # Use database values as source of truth
    uploader_id = str(user_record.user_id) if user_record.user_id is not None else None
    website_id = str(user_record.website_id) if user_record.website_id is not None else None
    
    logger.info(f"[UPLOAD] User validated: {username}, user_id: {uploader_id}, website_id: {website_id}")

    # Allowed file extensions
    allowed_extensions = {
        ext.strip().lower() for ext in settings.ALLOWED_FILE_TYPES.split(",") if ext.strip()
    }

    results: List[FileMeta] = []

    # Process each file individually to ensure partial success
    failed_files = []
    
    for uploaded_file in normalized_files:
        original_filename = uploaded_file.filename
        if not original_filename:
            logger.warning("[UPLOAD SKIP] File with no name encountered")
            continue
            
        try:
            safe_filename = sanitize_filename(original_filename)
            ext = safe_filename.split(".")[-1].lower() if "." in safe_filename else ""

            # Validate file type & size
            if not validate_file_extension(safe_filename, allowed_extensions):
                failed_files.append(f"{original_filename}: File type not allowed")
                logger.warning(f"[UPLOAD SKIP] File type not allowed: {original_filename}")
                continue

            # Read file content with detailed logging
            content = await uploaded_file.read()
            logger.info(f"[UPLOAD DEBUG] File '{original_filename}' read: content_type={type(content)}, is_none={content is None}, length={len(content) if content else 0}")
            
            if not content:
                failed_files.append(f"{original_filename}: File is empty")
                logger.warning(f"[UPLOAD SKIP] File content is empty or None for: {original_filename}")
                continue

            if not validate_file_size(len(content), settings.MAX_FILE_SIZE_MB):
                failed_files.append(f"{original_filename}: File too large")
                logger.warning(f"[UPLOAD SKIP] File too large: {original_filename}")
                continue

            # Parse text chunks for embedding
            text_chunks = parse_file(safe_filename, content)

            # --- Validate all parameters before saving ---
            logger.info(f"[SAVE FILE DEBUG] Validating parameters before save:")
            logger.info(f"  - uploader_id: {uploader_id} (type: {type(uploader_id)}, is_none: {uploader_id is None})")
            logger.info(f"  - website_id: {website_id} (type: {type(website_id)}, is_none: {website_id is None})")
            logger.info(f"  - db: {db} (type: {type(db)}, is_none: {db is None})")
            logger.info(f"  - collection_id: {collection_id} (type: {type(collection_id)}, is_none: {collection_id is None})")
            logger.info(f"  - safe_filename: {safe_filename} (type: {type(safe_filename)}, is_none: {safe_filename is None})")
            logger.info(f"  - content: length={len(content) if content else 0} (type: {type(content)}, is_none: {content is None})")
            
            # Explicit validation before calling save_file_with_website
            if uploader_id is None:
                failed_files.append(f"{original_filename}: uploader_id is None")
                logger.warning(f"[UPLOAD SKIP] uploader_id is None for: {original_filename}")
                continue
            if db is None:
                failed_files.append(f"{original_filename}: database session is None")
                logger.warning(f"[UPLOAD SKIP] database session is None for: {original_filename}")
                continue
            if safe_filename is None or not safe_filename:
                failed_files.append(f"{original_filename}: filename is None or empty")
                logger.warning(f"[UPLOAD SKIP] filename is None or empty for: {original_filename}")
                continue
            if content is None:
                failed_files.append(f"{original_filename}: file_content is None")
                logger.warning(f"[UPLOAD SKIP] file_content is None for: {original_filename}")
                continue
            
            # --- Save file using safe keyword-only approach ---
            file_metadata = file_storage_service.save_file_with_website(
                user_id=str(uploader_id) if uploader_id else None,
                website_id=str(website_id) if website_id else None,
                db=db,
                collection_id=collection_id,
                filename=safe_filename,
                file_content=content,
            )
            
            logger.info(f"[SAVE FILE SUCCESS] File saved with ID: {file_metadata.file_id}")

            file_id = str(file_metadata.file_id)
            vector_store = get_vector_store()

            for i, chunk in enumerate(text_chunks):
                metadata = {
                    "file_id": file_id,
                    "file_name": safe_filename,
                    "chunk_index": i,
                    "text": chunk,
                    "website_id": str(website_id) if website_id else None,
                    "collection_id": collection_id,
                    "uploader_id": str(uploader_id) if uploader_id else None
                }
                vector_store.add_document(chunk, metadata)

            file_storage_service.update_processing_status(file_id, "completed", len(text_chunks), db)

            meta = FileMeta(
                file_id=file_id,
                file_name=safe_filename,
                uploaded_by=current_user.get("username", "unknown"),
                uploader_id=str(uploader_id) if uploader_id else None,
                upload_timestamp=file_metadata.upload_timestamp.isoformat() if file_metadata.upload_timestamp is not None else None,
                file_size=int(str(file_metadata.file_size)) if file_metadata.file_size is not None else None,
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
                    "file_size": int(str(file_metadata.file_size)) if file_metadata.file_size is not None else 0,
                    "file_type": ext,
                    "chunk_count": len(text_chunks),
                    "collection_id": collection_id,
                },
            )

        except Exception as e:
            error_msg = f"File upload failed for {original_filename}: {str(e)}"
            failed_files.append(error_msg)
            logger.error(f"[UPLOAD ERROR] {error_msg}")
            # Continue with other files instead of failing the entire request
            continue

    # If all files failed, return an error
    if len(results) == 0 and len(normalized_files) > 0:
        logger.error(f"[UPLOAD COMPLETE FAILURE] All {len(normalized_files)} files failed to upload")
        raise HTTPException(status_code=500, detail=f"All files failed to upload. Errors: {'; '.join(failed_files)}")
    
    # Log results
    success_count = len(results)
    total_count = len(normalized_files)
    if failed_files:
        logger.warning(f"[UPLOAD PARTIAL SUCCESS] Uploaded {success_count}/{total_count} files. Failed files: {', '.join(failed_files)}")
    else:
        logger.info(f"[UPLOAD SUCCESS] Uploaded {success_count}/{total_count} files by {current_user.get('username')}")
    
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
    if current_user.get("role") not in {"user_admin", "super_admin"}:
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
    username = current_user.get("username")
    
    # Get user from database for reliable user_id and website_id
    if not username:
        raise HTTPException(status_code=401, detail="Username not found in token")
    
    user_record = db.query(User).filter(User.username == username).first()
    if not user_record:
        raise HTTPException(status_code=403, detail=f"User '{username}' not found in database")
    
    user_id = user_record.user_id
    website_id = user_record.website_id

    query = db.query(FileMetadata)

    # Super admin can view everything, optionally scoped to collection_id
    if role == "super_admin":
        if collection_id:
            query = query.filter(FileMetadata.collection_id == collection_id)
    elif role == "user_admin":
        # User admin: view files in collections they administer
        admin_collection_ids = [
            c.collection_id for c in db.query(Collection).filter(Collection.admin_user_id == user_id).all()
        ]
        if not admin_collection_ids:
            return []

        if collection_id:
            # Ensure requested collection is administered by this user
            if collection_id not in admin_collection_ids:
                raise HTTPException(status_code=403, detail="Access denied to this collection")
            query = query.filter(FileMetadata.collection_id == collection_id)
        else:
            query = query.filter(FileMetadata.collection_id.in_(admin_collection_ids))
    else:
        # Regular user: limit to same website (if available) or own uploads
        if collection_id:
            query = query.filter(FileMetadata.collection_id == collection_id)
        if website_id is not None:
            query = query.filter(FileMetadata.website_id == website_id)
        elif user_id is not None:
            query = query.filter(FileMetadata.uploader_id == user_id)

    files = query.order_by(FileMetadata.upload_timestamp.desc()).all()

    response_items: List[FileMeta] = []
    for record in files:
        uploader_username = str(record.uploader.username) if record.uploader and record.uploader.username else str(record.uploader_id)
        item = FileMeta(
            file_id=str(record.file_id),
            file_name=str(record.file_name),
            uploaded_by=uploader_username,
            uploader_id=str(record.uploader_id),
            upload_timestamp=record.upload_timestamp.isoformat() if record.upload_timestamp is not None else None,
            file_size=int(str(record.file_size)) if record.file_size is not None else None,
            processing_status=str(record.processing_status),
            collection_id=str(record.collection_id) if record.collection_id is not None else None,
        )
        response_items.append(item)
        file_metadata_db[str(record.file_id)] = item

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
    """Download original file by file_id or file_name using collection_id for access control"""
    from app.models.user import User
    from app.models.collection import CollectionUser

    role = current_user.get("role")
    username = current_user.get("username")
    
    # Get user from database
    if not username:
        raise HTTPException(status_code=401, detail="Username not found in token")
    
    user_record = db.query(User).filter(User.username == username).first()
    if not user_record:
        raise HTTPException(status_code=403, detail=f"User '{username}' not found in database")
    
    current_user_id = user_record.user_id

    # Try to find by file_id first
    file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == identifier).first()

    # If not found, try by file_name
    if not file_metadata:
        file_metadata = db.query(FileMetadata).filter(FileMetadata.file_name == identifier).first()

    if not file_metadata:
        raise HTTPException(status_code=404, detail="File metadata not found")

    # --- Permission check ---
    if role == "super_admin":
        pass  # full access
    elif role == "user_admin":
        # User admin can access files in collections they administer
        from app.models.collection import Collection
        administered_collection = db.query(Collection).filter(
            Collection.collection_id == file_metadata.collection_id,
            Collection.admin_user_id == current_user_id
        ).first()
        
        if not administered_collection:
            raise HTTPException(status_code=403, detail="You don't have permission to access this file")
    elif role in {"user", "plugin_user"}:
        # Regular or plugin users can access files in collections they're members of
        if file_metadata.collection_id is None:
            raise HTTPException(status_code=403, detail="File has no collection assignment")
        
        membership = db.query(CollectionUser).filter(
            CollectionUser.collection_id == file_metadata.collection_id,
            CollectionUser.user_id == current_user_id
        ).first()
        
        if not membership:
            raise HTTPException(status_code=403, detail="You don't have access to this collection")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    # --- Fetch file binary ---
    file_storage_service = FileStorageService()
    binary_record = file_storage_service.get_file_binary(str(file_metadata.file_id), db)

    if not binary_record or binary_record.data is None:
        raise HTTPException(status_code=404, detail="File data not found")

    filename = file_metadata.file_name or f"download-{file_metadata.file_id}"
    media_type = binary_record.mime_type or file_metadata.file_type or "application/octet-stream"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }

    data_bytes = bytes(str(binary_record.data), 'utf-8') if binary_record.data is not None else b''
    return StreamingResponse(iter([data_bytes]), media_type=str(media_type), headers=headers)



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
    username = current_user.get("username")
    
    # Get user from database
    if not username:
        raise HTTPException(status_code=401, detail="Username not found in token")
    
    user_record = db.query(User).filter(User.username == username).first()
    if not user_record:
        raise HTTPException(status_code=403, detail=f"User '{username}' not found in database")
    
    current_user_id = user_record.user_id
    current_user_website = user_record.website_id

    if role != "super_admin" and file_metadata.website_id is not None and current_user_website is not None and str(file_metadata.website_id) != str(current_user_website):
        raise HTTPException(status_code=403, detail="File belongs to a different website")

    if role not in {"user_admin", "super_admin"}:
        # Convert to string values for comparison to avoid boolean evaluation error
        file_uploader_id = str(file_metadata.uploader_id) if file_metadata.uploader_id is not None else None
        user_id_str = str(current_user_id) if current_user_id is not None else None
        if not user_id_str or (file_uploader_id is not None and user_id_str is not None and file_uploader_id != user_id_str):
            raise HTTPException(status_code=403, detail="Permission denied")

    return file_metadata.to_dict()


# ------------------------
# Debug endpoint - Vector DB stats
# ------------------------
@router.get("/debug/vector-stats")
async def get_vector_stats(current_user: dict = Depends(get_current_user)):
    """Debug endpoint to check vector database contents"""
    if current_user.get("role") not in {"user_admin", "super_admin"}:
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
