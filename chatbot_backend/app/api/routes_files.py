# app/api/routes_files.py

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from typing import List
from uuid import uuid4
from app.core.vector_singleton import get_vector_store
from app.core.cache import Cache
from app.utils.file_parser import parse_file
from app.models.file import FileMeta
from app.api.routes_auth import get_current_user
from app.config import settings
import logging

logger = logging.getLogger("files_logger")
logging.basicConfig(level=logging.INFO)

router = APIRouter()
cache = Cache()  # Redis cache utility

# In-memory metadata store for MVP (replace with DB in production)
file_metadata_db = {}

# ------------------------
# Upload file endpoint
# ------------------------
@router.post("/upload", response_model=FileMeta)
async def upload_file(
    uploaded_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
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

    # Generate unique file ID
    file_id = str(uuid4())

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
    
    # Debug: Check if documents were actually stored
    if vector_store.client is None:
        logger.info(f"[UPLOAD DEBUG] Total documents in fallback storage: {len(vector_store.documents)}")
    else:
        logger.info(f"[UPLOAD DEBUG] Documents stored in Qdrant collection: {vector_store.collection_name}")

    # Store metadata
    metadata = FileMeta(
        file_id=file_id,
        file_name=uploaded_file.filename,
        uploaded_by=current_user["username"]
    )
    file_metadata_db[file_id] = metadata

    logger.info(f"File uploaded: {uploaded_file.filename} by {current_user['username']}")

    return metadata


# ------------------------
# Delete file endpoint
# ------------------------
@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    # Check if user has admin role
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can delete files")
    if file_id not in file_metadata_db:
        raise HTTPException(status_code=404, detail="File not found")

    # Remove all chunks for this file from vector store
    vector_store = get_vector_store()
    vector_store.delete_documents_by_file_id(file_id)

    # Remove metadata
    del file_metadata_db[file_id]

    # Invalidate cache (all cached answers containing this file)
    # For MVP, we can flush all FAQ cache or implement smarter invalidation later
    if cache.client:
        cache.client.flushdb()
        logger.info(f"Cache invalidated due to deletion of file {file_id}")

    logger.info(f"File deleted: {file_id} by {current_user['username']}")

    return {"detail": f"File {file_id} deleted successfully"}


# ------------------------
# List files endpoint
# ------------------------
@router.get("/list", response_model=List[FileMeta])
async def list_files(current_user: dict = Depends(get_current_user)):
    return list(file_metadata_db.values())


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
