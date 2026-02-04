# app/api/routes_files.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from collections.abc import Sequence
from app.core.vector_singleton import get_vector_store
from app.core.database import get_db
from app.core.permissions import get_current_user
# from app.utils.file_parser import parse_file  # Removed in favor of FileIngestionService
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
from app.services.file_ingestion_service import FileIngestionService
from pydantic import BaseModel
import logging
from uuid import uuid4
import os

logger = logging.getLogger("files_logger")
logging.basicConfig(level=logging.INFO)

router = APIRouter()

# Security for plugin tokens
plugin_security = HTTPBearer()

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
    source_type: Optional[str] = "file"  # "file" or "crawled"
    # Crawled data fields
    crawl_job_id: Optional[str] = None
    target_url: Optional[str] = None
    pages_crawled: Optional[int] = None
    chunks_created: Optional[int] = None

# In-memory metadata store for MVP (replace with DB in production)
file_metadata_db = {}

# Global upload tracking - limit to 10 concurrent uploads
MAX_CONCURRENT_UPLOADS = 10
_active_uploads: set = set()  # Set of file_ids currently being processed
_upload_lock = __import__('threading').Lock()


def _get_upload_status() -> dict:
    """Get current upload status."""
    with _upload_lock:
        return {
            "active_upload_count": len(_active_uploads),
            "max_concurrent": MAX_CONCURRENT_UPLOADS,
            "can_upload": len(_active_uploads) < MAX_CONCURRENT_UPLOADS,
            "available_slots": MAX_CONCURRENT_UPLOADS - len(_active_uploads)
        }


def _acquire_upload_slot(file_id: str) -> bool:
    """Try to acquire an upload slot. Returns True if successful."""
    with _upload_lock:
        if len(_active_uploads) >= MAX_CONCURRENT_UPLOADS:
            return False
        _active_uploads.add(file_id)
        return True


def _release_upload_slot(file_id: str):
    """Release an upload slot."""
    with _upload_lock:
        _active_uploads.discard(file_id)


def _trigger_capability_scan_async(collection_id: str):
    """
    Trigger an async capability scan for a collection after file upload.
    This updates the collection's knowledge of what topics it can help with.
    """
    try:
        from app.core.database import SessionLocal
        from app.services.capabilities_scanner import scan_and_update_collection
        
        db = SessionLocal()
        try:
            scan_and_update_collection(collection_id, db, force=False)  # force=False to respect cooldown
            logger.info(f"[UPLOAD] Capability scan completed for {collection_id}")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[UPLOAD] Capability scan failed: {e}")


# ------------------------
# Upload status endpoint
# ------------------------
@router.get("/upload/status")
async def get_upload_status(current_user: User = Depends(get_current_user)):
    """Get current file upload status including active uploads."""
    return _get_upload_status()


# ------------------------
# Upload file endpoint
# ------------------------
@router.post("/upload", response_model=List[FileMeta])
async def upload_file(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    uploaded_files: Optional[Union[UploadFile, List[UploadFile]]] = File(None, alias="uploaded_files"),
    single_file: Optional[UploadFile] = File(None, alias="file"),
    collection_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Upload one or multiple files"""
    logger.debug(f"[UPLOAD DEBUG] Upload request from user: {getattr(current_user, 'username', None)}, role: {getattr(current_user, 'role', None)}")
    
    # Debug: Log what files we received
    logger.debug(f"[UPLOAD DEBUG] Received files: {files is not None}")
    logger.debug(f"[UPLOAD DEBUG] Received uploaded_files: {uploaded_files is not None}")
    logger.debug(f"[UPLOAD DEBUG] Received single_file: {single_file is not None}")
    logger.debug(f"[UPLOAD DEBUG] Received collection_id: {collection_id}")
    
    # Additional debug info for uploaded_files
    if uploaded_files:
        if isinstance(uploaded_files, list):
            logger.debug(f"[UPLOAD DEBUG] uploaded_files is a list with {len(uploaded_files)} items")
            for i, uf in enumerate(uploaded_files):
                logger.debug(f"[UPLOAD DEBUG] uploaded_files[{i}].filename: {getattr(uf, 'filename', 'None')}")
        else:
            logger.debug(f"[UPLOAD DEBUG] uploaded_files is a single file: {getattr(uploaded_files, 'filename', 'None')}")

    # Check permissions
    role = getattr(current_user, 'role', None)
    if role not in ["user_admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can upload files")

    # Check upload limit
    upload_status = _get_upload_status()
    if not upload_status["can_upload"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Upload limit reached. {upload_status['active_upload_count']} files are being processed. Maximum allowed: {MAX_CONCURRENT_UPLOADS}. Please wait and try again."
        )

    # Create a unique upload session ID and acquire a slot
    upload_session_id = f"upload_{uuid4().hex[:8]}"
    if not _acquire_upload_slot(upload_session_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload limit reached. Please wait and try again."
        )
    
    try:
        # Note: The rest of the function is wrapped in this try block
        # The finally block at the end will release the slot

        # Normalize files
        normalized_files: List[UploadFile] = []

        def _add_candidates(group):
            logger.debug(f"[UPLOAD DEBUG] _add_candidates called with group: {type(group)}")
            if not group:
                logger.debug("[UPLOAD DEBUG] _add_candidates: group is falsy, returning")
                return
            logger.debug(f"[UPLOAD DEBUG] _add_candidates: group is not falsy")
            
            if isinstance(group, Sequence) and not isinstance(group, (str, bytes)):
                items = list(group)
                logger.debug(f"[UPLOAD DEBUG] _add_candidates: group is Sequence, items count: {len(items)}")
            else:
                items = [group]
                logger.debug(f"[UPLOAD DEBUG] _add_candidates: group is not Sequence, items count: {len(items)}")
                
            for i, candidate in enumerate(items):
                logger.debug(f"[UPLOAD DEBUG] _add_candidates: checking candidate {i}: {type(candidate)}")
                if candidate:
                    logger.debug(f"[UPLOAD DEBUG] _add_candidates: candidate {i} is truthy")
                    # Accept both FastAPI and Starlette UploadFile via duck typing
                    filename = getattr(candidate, "filename", None)
                    has_read = hasattr(candidate, "read")
                    if filename and has_read:
                        logger.info(f"[UPLOAD DEBUG] _add_candidates: candidate {i} appears to be UploadFile-like, filename: {filename}")
                        normalized_files.append(candidate)
                        logger.info(f"[UPLOAD DEBUG] Added file: {filename}")
                    else:
                        logger.info(f"[UPLOAD DEBUG] _add_candidates: candidate {i} is not UploadFile-like: {type(candidate)} (filename={filename}, has_read={has_read})")
                else:
                    logger.info(f"[UPLOAD DEBUG] _add_candidates: candidate {i} is falsy")

        # Prefer robust extraction from raw multipart form to avoid framework type mismatches
        try:
            form = await request.form()
            # Collect all UploadFile-like values from the form, regardless of field name
            for key in form.keys():
                values = form.getlist(key)
                for v in values:
                    # Skip non-file fields (e.g., collection_id)
                    if hasattr(v, "filename") and hasattr(v, "read"):
                        _add_candidates([v])
        except Exception as form_err:
            logger.debug(f"[UPLOAD DEBUG] Failed to read raw multipart form: {form_err}")

        # Also add from annotated params (in case framework populated them)
        _add_candidates(files)
        _add_candidates(uploaded_files)
        if single_file and getattr(single_file, "filename", None):
            normalized_files.append(single_file)
            logger.debug(f"[UPLOAD DEBUG] Added single file: {single_file.filename}")

        logger.debug(f"[UPLOAD DEBUG] Total normalized files: {len(normalized_files)}")
        
        if not normalized_files:
            logger.error("[UPLOAD ERROR] No files provided for upload - files list is empty")
            raise HTTPException(status_code=400, detail="No files provided for upload")

        # Get user from database using username (most reliable)
        username = getattr(current_user, 'username', None)
        if not username:
            raise HTTPException(status_code=401, detail="Username not found in token")
        
        user_record = db.query(User).filter(User.username == username).first()
        if not user_record:
            raise HTTPException(status_code=403, detail=f"User '{username}' not found in database")
        
        # Use database values as source of truth
        uploader_id = str(user_record.user_id) if user_record.user_id is not None else None
        website_id = str(user_record.website_id) if user_record.website_id is not None else None
        
        logger.debug(f"[UPLOAD] User validated: {username}, user_id: {uploader_id}, website_id: {website_id}")

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
                logger.debug(f"[UPLOAD DEBUG] File '{original_filename}' read: content_type={type(content)}, is_none={content is None}, length={len(content) if content else 0}")
                
                if not content:
                    failed_files.append(f"{original_filename}: File is empty")
                    logger.warning(f"[UPLOAD SKIP] File content is empty or None for: {original_filename}")
                    continue

                if not validate_file_size(len(content), settings.MAX_FILE_SIZE_MB):
                    failed_files.append(f"{original_filename}: File too large")
                    logger.warning(f"[UPLOAD SKIP] File too large: {original_filename}")
                    continue

                # Parse text chunks for embedding
                # text_chunks = parse_file(safe_filename, content) # REPLACED with background processing

                # --- Validate all parameters before saving ---
                logger.debug(f"[SAVE FILE DEBUG] Validating parameters before save:")
                logger.debug(f"  - uploader_id: {uploader_id} (type: {type(uploader_id)}, is_none: {uploader_id is None})")
                logger.debug(f"  - website_id: {website_id} (type: {type(website_id)}, is_none: {website_id is None})")
                logger.debug(f"  - db: {db} (type: {type(db)}, is_none: {db is None})")
                logger.debug(f"  - collection_id: {collection_id} (type: {type(collection_id)}, is_none: {collection_id is None})")
                logger.debug(f"  - safe_filename: {safe_filename} (type: {type(safe_filename)}, is_none: {safe_filename is None})")
                logger.debug(f"  - content: length={len(content) if content else 0} (type: {type(content)}, is_none: {content is None})")
                
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
                
                logger.debug(f"[SAVE FILE SUCCESS] File saved with ID: {file_metadata.file_id}")

                file_id = str(file_metadata.file_id)
                
                # --- Background Processing ---
                # Trigger ingestion service in background
                # We don't wait for embedding here
                
                # Initialize service (db session logic handled in background method)
                ingestion_service = FileIngestionService(db)
                background_tasks.add_task(
                    ingestion_service.process_file_background,
                    file_id=file_id,
                    user_id=str(uploader_id)
                )

                # vector_store = get_vector_store()
                # for i, chunk in enumerate(text_chunks):
                #     metadata = {
                #         "file_id": file_id,
                #         "file_name": safe_filename,
                #         "chunk_index": i,
                #         "text": chunk,
                #         "website_id": str(website_id) if website_id else None,
                #         "collection_id": collection_id,
                #         "uploader_id": str(uploader_id) if uploader_id else None
                #     }
                #     vector_store.add_document(chunk, metadata)

                # Status is "processing" initially (from save_file_with_website)
                # file_storage_service.update_processing_status(file_id, "completed", len(text_chunks), db)

                meta = FileMeta(
                    file_id=file_id,
                    file_name=safe_filename,
                    uploaded_by=getattr(current_user, 'username', 'unknown'),
                    uploader_id=str(uploader_id) if uploader_id else None,
                    upload_timestamp=file_metadata.upload_timestamp.isoformat() if file_metadata.upload_timestamp is not None else None,
                    file_size=int(str(file_metadata.file_size)) if file_metadata.file_size is not None else None,
                    processing_status="processing", # Start as processing
                    collection_id=collection_id,
                )

                results.append(meta)
                file_metadata_db[file_id] = meta

                activity_tracker.log_activity(
                    activity_type="file_upload",
                    user=getattr(current_user, 'username', 'unknown'),
                    details={
                        "file_name": safe_filename,
                        "file_id": file_id,
                        "file_size": int(str(file_metadata.file_size)) if file_metadata.file_size is not None else 0,
                        "file_type": ext,
                        "status": "processing",
                        # "chunk_count": len(text_chunks),
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
            logger.debug(f"[UPLOAD SUCCESS] Uploaded {success_count}/{total_count} files by {getattr(current_user, 'username', 'unknown')}")
        
        # Trigger capability scan after successful uploads (background task)
        if success_count > 0 and collection_id:
            background_tasks.add_task(_trigger_capability_scan_async, collection_id)
        
        return results
    finally:
        # Always release the upload slot when done
        _release_upload_slot(upload_session_id)


# ------------------------
# Delete file endpoint
# ------------------------
@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user has admin role
    role = getattr(current_user, 'role', None)
    if role not in {"user_admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only admin users can delete files")

    # Handle Crawl Job Deletion
    if file_id.startswith("crawl_"):
        job_id = file_id.replace("crawl_", "")
        from app.models.crawler_job import CrawlerJob
        from app.services.crawler_service import CrawlerService
        
        job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        if not job:
             raise HTTPException(status_code=404, detail="Crawl job not found")
             
        # Permission check for crawl job
        if role != "super_admin":
             # If not superadmin, ensure user owns the job or admin owns the collection
             if job.user_id != current_user.user_id:
                  # Check if user is admin of the collection
                  collection = db.query(Collection).filter(Collection.collection_id == job.collection_id).first()
                  if not collection or collection.admin_user_id != current_user.user_id:
                       raise HTTPException(status_code=403, detail="Access denied to delete this crawl job")

        # Delete using crawler service
        crawler_service = CrawlerService(db)
        success = crawler_service.delete_job(job_id)
        
        if success:
             logger.info(f"User {current_user.username} deleted crawl job {job_id} via files endpoint")
             activity_tracker.log_activity(
                activity_type="crawl_deleted",
                user=getattr(current_user, 'username', 'unknown'),
                details={
                    "job_id": job_id,
                    "source": "files_list"
                }
             )
             return {"detail": f"Crawl data deleted successfully"}
        else:
             raise HTTPException(status_code=500, detail="Failed to delete crawl data")

    # Regular File Deletion
    file_record = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Check permissions for regular file
        if role != "super_admin":
            current_user_id = str(current_user.user_id) if hasattr(current_user, 'user_id') else None
            is_owner = str(file_record.uploader_id) == current_user_id
            
            # Check collection admin status
            is_collection_admin = False
            if file_record.collection_id:
                collection = db.query(Collection).filter(Collection.collection_id == file_record.collection_id).first()
                if collection and str(collection.admin_user_id) == current_user_id:
                    is_collection_admin = True
            
            if not is_owner and not is_collection_admin:
                 raise HTTPException(status_code=403, detail="Access denied")

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
                logger.debug(f"Cache invalidated due to deletion of file {file_id}")
        except Exception as cache_error:
            logger.warning(f"Failed to invalidate cache: {cache_error}")

        logger.debug(f"File deleted: {file_id} by {getattr(current_user, 'username', 'unknown')}")
        
        # Log activity
        activity_tracker.log_activity(
            activity_type="file_delete",
            user=getattr(current_user, 'username', 'unknown'),
            details={
                "file_id": file_id,
                "file_name": file_record.file_name,
            }
        )
        
        return {"detail": f"File {file_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


# ------------------------
# List files endpoint
# ------------------------
@router.get("/list", response_model=List[FileMeta])
async def list_files(
    collection_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    role = str(current_user.role) if hasattr(current_user, 'role') else None
    username = str(current_user.username) if hasattr(current_user, 'username') else None
    
    # Get user from database for reliable user_id and website_id
    if not username:
        raise HTTPException(status_code=401, detail="Username not found in token")
    
    user_record = db.query(User).filter(User.username == username).first()
    if not user_record:
        raise HTTPException(status_code=403, detail=f"User '{username}' not found in database")
    
    user_id = str(user_record.user_id) if hasattr(user_record, 'user_id') and user_record.user_id is not None else None
    website_id = str(user_record.website_id) if hasattr(user_record, 'website_id') and user_record.website_id is not None else None

    query = db.query(FileMetadata)

    # Super admin can view everything, optionally scoped to collection_id
    if role == "super_admin":
        if collection_id:
            query = query.filter(FileMetadata.collection_id == collection_id)
    elif role == "user_admin":
        # User admin: view files in collections they administer
        admin_collection_ids = [
            str(c.collection_id) for c in db.query(Collection).filter(Collection.admin_user_id == user_id).all()
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
        uploader_username = str(record.uploader.username) if record.uploader and hasattr(record.uploader, 'username') and record.uploader.username else str(record.uploader_id)
        item = FileMeta(
            file_id=str(record.file_id),
            file_name=str(record.file_name),
            uploaded_by=uploader_username,
            uploader_id=str(record.uploader_id),
            upload_timestamp=record.upload_timestamp.isoformat() if record.upload_timestamp is not None else None,
            file_size=int(str(record.file_size)) if record.file_size is not None else None,
            processing_status=str(record.processing_status),
            collection_id=str(record.collection_id) if record.collection_id is not None else None,
            source_type="file",
        )
        response_items.append(item)
        file_metadata_db[str(record.file_id)] = item

    # Add crawl jobs for the collection if collection_id is provided
    if collection_id:
        try:
            from app.models.crawler_job import CrawlerJob
            crawl_jobs_query = db.query(CrawlerJob).filter(CrawlerJob.collection_id == collection_id)
            
            # Apply same permission filters for crawl jobs
            if role == "super_admin":
                pass  # Can see all
            elif role == "user_admin":
                # User admin: view crawl jobs in collections they administer
                admin_collection_ids = [
                    str(c.collection_id) for c in db.query(Collection).filter(Collection.admin_user_id == user_id).all()
                ]
                if collection_id not in admin_collection_ids:
                    crawl_jobs_query = crawl_jobs_query.filter(False)  # No access
            else:
                # Regular user: only own crawl jobs
                if user_id is not None:
                    crawl_jobs_query = crawl_jobs_query.filter(CrawlerJob.user_id == user_id)
                else:
                    crawl_jobs_query = crawl_jobs_query.filter(False)  # No access
            
            crawl_jobs = crawl_jobs_query.order_by(CrawlerJob.created_at.desc()).all()
            
            for job in crawl_jobs:
                # Only include completed or running jobs that have crawled pages
                if job.status in ["completed", "running"] and job.pages_crawled > 0:
                    # Get user info for the crawl job
                    job_user = db.query(User).filter(User.user_id == job.user_id).first()
                    job_username = str(job_user.username) if job_user and hasattr(job_user, 'username') and job_user.username else "System"
                    
                    # Use job_id as file_id for crawled data
                    crawl_item = FileMeta(
                        file_id=f"crawl_{job.job_id}",
                        file_name=f"Crawled: {job.target_url}",
                        uploaded_by=job_username,
                        uploader_id=str(job.user_id) if job.user_id else None,
                        upload_timestamp=job.created_at.isoformat() if job.created_at else None,
                        file_size=job.total_characters if job.total_characters else 0,  # Use total_characters as file size
                        processing_status=job.status,
                        collection_id=str(job.collection_id) if job.collection_id else None,
                        source_type="crawled",
                        crawl_job_id=str(job.job_id),
                        target_url=job.target_url,
                        pages_crawled=job.pages_crawled,
                        chunks_created=job.chunks_created if hasattr(job, 'chunks_created') else None,
                    )
                    response_items.append(crawl_item)
        except Exception as e:
            logger.warning(f"Failed to fetch crawl jobs: {e}")
            # Continue without crawl jobs if there's an error

    return response_items


# ------------------------
# Download file endpoint
# ------------------------
@router.get("/download/{identifier}")
async def download_file(
    identifier: str,
    credentials: HTTPAuthorizationCredentials = Depends(plugin_security),
    db: Session = Depends(get_db)
):
    """Download original file by file_id or file_name using collection_id for access control"""
    from app.models.user import User
    from app.models.collection import CollectionUser
    from app.core.auth import decode_plugin_user_token
    import json

    # Try to authenticate as plugin user first, then as regular user
    current_user = None
    role = None
    username = None
    current_user_id = None
    
    try:
        # Try to decode as plugin token first
        token_payload = decode_plugin_user_token(credentials.credentials)
        
        # Get plugin user from database
        user_record = db.query(User).filter(
            User.username == token_payload["username"],
            User.role == "plugin_user",
            User.is_active == True
        ).first()
        
        # Extract values from SQLAlchemy model instances
        user_record_plugin_token = str(user_record.plugin_token) if user_record and hasattr(user_record, 'plugin_token') else None
        credentials_token = str(credentials.credentials) if credentials and hasattr(credentials, 'credentials') else None
        
        if user_record and user_record_plugin_token == credentials_token:
            current_user = user_record
            role = "plugin_user"
            username = str(user_record.username) if hasattr(user_record, 'username') else None
            current_user_id = str(user_record.user_id) if hasattr(user_record, 'user_id') else None
    except ValueError:
        # Not a plugin token, try regular user authentication
        pass
    
    # If plugin authentication failed, try regular user authentication
    if current_user is None:
        try:
            # This is the existing authentication logic
            from app.core.permissions import get_current_user
            user_record = get_current_user(credentials, db)
            current_user = user_record
            role = user_record.role
            username = user_record.username
            current_user_id = user_record.user_id
        except:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    # Handle crawled data download (crawl_ prefixed identifiers)
    if identifier.startswith("crawl_"):
        job_id = identifier.replace("crawl_", "")
        from app.models.crawler_job import CrawlerJob
        
        job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Crawl job not found")
        
        # Permission check for crawl job
        role_str = str(role) if role is not None else ""
        if role_str == "super_admin":
            pass  # Full access
        elif role_str == "user_admin":
            # User admin can access crawl jobs in collections they administer
            administered_collection = db.query(Collection).filter(
                Collection.collection_id == job.collection_id,
                Collection.admin_user_id == current_user_id
            ).first()
            if not administered_collection:
                raise HTTPException(status_code=403, detail="You don't have permission to access this crawl data")
        elif role_str in {"user", "plugin_user"}:
            # Regular or plugin users can access crawl jobs in collections they're members of
            if job.collection_id is None:
                raise HTTPException(status_code=403, detail="Crawl job has no collection assignment")
            
            membership = db.query(CollectionUser).filter(
                CollectionUser.collection_id == job.collection_id,
                CollectionUser.user_id == current_user_id
            ).first()
            
            if not membership:
                raise HTTPException(status_code=403, detail="You don't have access to this collection")
            
            # For plugin users, also check specific download permission
            if role_str == "plugin_user" and not membership.can_download:
                raise HTTPException(status_code=403, detail="Plugin user does not have download permission")
        else:
            raise HTTPException(status_code=403, detail="Invalid role")
        
        # Build export data from crawl job metadata
        export_data = {
            "job_id": job.job_id,
            "target_url": job.target_url,
            "status": job.status,
            "pages_discovered": job.pages_discovered,
            "pages_crawled": job.pages_crawled,
            "pages_skipped": job.pages_skipped,
            "pages_failed": job.pages_failed,
            "chunks_created": job.chunks_created,
            "total_characters": job.total_characters,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "crawled_urls": job.crawled_urls or [],
            "failed_urls": job.failed_urls or [],
            "skipped_urls": job.skipped_urls or [],
        }
        
        # Generate filename from target URL
        from urllib.parse import urlparse
        parsed_url = urlparse(job.target_url)
        domain = parsed_url.netloc.replace(".", "_")
        filename = f"crawl_data_{domain}_{job_id[:8]}.json"
        
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        
        # Use streaming JSON generator for memory-efficient downloads
        async def stream_crawl_json():
            """Generator that streams JSON content without loading all chunks into memory."""
            # Start JSON object
            yield '{\n'
            
            # Write metadata fields first
            metadata_fields = ["job_id", "target_url", "status", "pages_discovered", 
                             "pages_crawled", "pages_skipped", "pages_failed", 
                             "chunks_created", "total_characters", "created_at", 
                             "started_at", "completed_at", "crawled_urls", 
                             "failed_urls", "skipped_urls"]
            
            for i, field in enumerate(metadata_fields):
                value = export_data.get(field)
                json_value = json.dumps(value, ensure_ascii=False)
                yield f'  "{field}": {json_value}'
                yield ',\n'
            
            # Stream crawled content array
            yield '  "crawled_content": [\n'
            
            try:
                vector_store = get_vector_store()
                content_by_url = {}
                total_chunks = 0
                
                # Process chunks in batches using the iterator
                for batch in vector_store.iter_documents_by_crawl_job_id(job_id, batch_size=100):
                    for chunk in batch:
                        payload = chunk.get("payload", {})
                        source_url = payload.get("source_url", "unknown")
                        text = payload.get("text", "")
                        title = payload.get("page_title", "")
                        chunk_index = payload.get("chunk_index", 0)
                        
                        if source_url not in content_by_url:
                            content_by_url[source_url] = {
                                "title": title,
                                "url": source_url,
                                "chunks": []
                            }
                        
                        content_by_url[source_url]["chunks"].append({
                            "chunk_index": chunk_index,
                            "text": text
                        })
                        total_chunks += 1
                
                # Sort chunks within each URL and stream the results
                url_list = list(content_by_url.values())
                for url_data in url_list:
                    url_data["chunks"].sort(key=lambda x: x.get("chunk_index", 0))
                
                # Stream each page's content
                for i, page_data in enumerate(url_list):
                    page_json = json.dumps(page_data, indent=4, ensure_ascii=False)
                    # Indent each line for proper formatting
                    indented = '\n'.join('    ' + line for line in page_json.split('\n'))
                    yield indented
                    if i < len(url_list) - 1:
                        yield ',\n'
                    else:
                        yield '\n'
                
                yield '  ],\n'
                yield f'  "total_chunks_exported": {total_chunks}\n'
                
                logger.info(f"Streamed {total_chunks} chunks from {len(url_list)} pages for crawl job {job_id}")
                
            except Exception as e:
                logger.warning(f"Failed to stream crawled content from vector store: {e}")
                yield '  ],\n'
                yield f'  "content_export_error": {json.dumps(str(e))}\n'
            
            # Close JSON object
            yield '}\n'
        
        logger.info(f"User {username} streaming crawl job {job_id} as JSON")
        return StreamingResponse(stream_crawl_json(), media_type="application/json", headers=headers)
    
    # Try to find by file_id first (for regular files)
    file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == identifier).first()

    # If not found, try by file_name
    if not file_metadata:
        file_metadata = db.query(FileMetadata).filter(FileMetadata.file_name == identifier).first()

    if not file_metadata:
        raise HTTPException(status_code=404, detail="File metadata not found")

    # --- Permission check ---
    role_str = str(role) if role is not None else ""
    if role_str == "super_admin":
        pass  # full access
    elif role_str == "user_admin":
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
        
        # For plugin users, also check specific download permission
        if role == "plugin_user" and not membership.can_download:
            raise HTTPException(status_code=403, detail="Plugin user does not have download permission")
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

    # Return the raw binary bytes without any string conversion to avoid corruption
    data_bytes = binary_record.data if binary_record.data is not None else b""
    # Ensure we have bytes, handling SQLAlchemy column objects
    if hasattr(data_bytes, 'tobytes') and callable(getattr(data_bytes, 'tobytes', None)):
        data_bytes = data_bytes.tobytes()
    elif not isinstance(data_bytes, bytes):
        # If it's not bytes and doesn't have tobytes, try to convert it
        try:
            # Check if it's a SQLAlchemy column object
            if hasattr(data_bytes, 'value'):
                data_bytes = bytes(data_bytes.value) if data_bytes.value else b""
            else:
                data_bytes = bytes(data_bytes) if data_bytes else b""
        except:
            data_bytes = b""
    return StreamingResponse(iter([data_bytes]), media_type=str(media_type), headers=headers)


# ------------------------
# Download file by name and collection endpoint
# ------------------------
@router.get("/download/by-name/{collection_id}/{file_name}")
async def download_file_by_name(
    collection_id: str,
    file_name: str,
    credentials: HTTPAuthorizationCredentials = Depends(plugin_security),
    db: Session = Depends(get_db)
):
    """Download original file by file_name and collection_id for access control"""
    from app.models.user import User
    from app.models.collection import CollectionUser
    from app.core.auth import decode_plugin_user_token

    # Try to authenticate as plugin user first, then as regular user
    current_user = None
    role = None
    username = None
    current_user_id = None
    
    try:
        # Try to decode as plugin token first
        token_payload = decode_plugin_user_token(credentials.credentials)
        
        # Get plugin user from database
        user_record = db.query(User).filter(
            User.username == token_payload["username"],
            User.role == "plugin_user",
            User.is_active == True
        ).first()
        
        if user_record and user_record.plugin_token == credentials.credentials:
            current_user = user_record
            role = "plugin_user"
            username = user_record.username
            current_user_id = user_record.user_id
    except ValueError:
        # Not a plugin token, try regular user authentication
        pass
    
    # If plugin authentication failed, try regular user authentication
    if current_user is None:
        try:
            # This is the existing authentication logic
            from app.core.permissions import get_current_user
            user_record = get_current_user(credentials, db)
            current_user = user_record
            role = user_record.role
            username = user_record.username
            current_user_id = user_record.user_id
        except:
            raise HTTPException(status_code=401, detail="Could not validate credentials")

    # Find file by file_name and collection_id
    file_metadata = db.query(FileMetadata).filter(
        FileMetadata.file_name == file_name,
        FileMetadata.collection_id == collection_id
    ).first()

    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")

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
        
        # For plugin users, also check specific download permission
        if role == "plugin_user" and not membership.can_download:
            raise HTTPException(status_code=403, detail="Plugin user does not have download permission")
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

    # Return the raw binary bytes without any string conversion to avoid corruption
    data_bytes = binary_record.data if binary_record.data is not None else b""
    return StreamingResponse(iter([data_bytes]), media_type=str(media_type), headers=headers)


# ------------------------
# Get file metadata endpoint
# ------------------------
@router.get("/metadata/{file_id}")
async def get_file_metadata(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get file metadata by file_id"""
    file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
    
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    role = getattr(current_user, 'role', None)
    username = getattr(current_user, 'username', None)
    
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
async def get_vector_stats(current_user: User = Depends(get_current_user)):
    """Debug endpoint to check vector database contents"""
    role = getattr(current_user, 'role', None)
    if role not in {"user_admin", "super_admin"}:
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

# Add security scheme for plugin tokens
plugin_security = HTTPBearer()
