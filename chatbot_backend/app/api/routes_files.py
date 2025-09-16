# app/api/routes_files.py

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from typing import List
from uuid import uuid4
from app.core.vectorstore import VectorStore
from app.core.cache import Cache
from app.utils.file_parser import parse_file
from app.models.file import FileMeta
from app.api.routes_auth import get_current_user
from app.config import settings
import logging

logger = logging.getLogger("files_logger")
logging.basicConfig(level=logging.INFO)

router = APIRouter()
vector_store = VectorStore(settings.VECTOR_DB_URL)
cache = Cache()  # Redis cache utility

# In-memory metadata store for MVP (replace with DB in production)
file_metadata_db = {}

# ------------------------
# Upload file endpoint
# ------------------------
@router.post("/upload", response_model=FileMeta)
async def upload_file(
    uploaded_file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    # Validate file type
    ext = uploaded_file.filename.split('.')[-1].lower()
    if ext not in settings.ALLOWED_FILE_TYPES.split(','):
        raise HTTPException(status_code=400, detail="File type not allowed")

    # Read file content
    content = await uploaded_file.read()
    text_chunks = parse_file(uploaded_file.filename, content)

    # Generate unique file ID
    file_id = str(uuid4())

    # Store embeddings in Qdrant
    for i, chunk in enumerate(text_chunks):
        chunk_metadata = {
            "file_id": file_id,
            "file_name": uploaded_file.filename,
            "chunk_index": i,
            "text": chunk
        }
        vector_store.add_document(chunk, chunk_metadata)

    # Store metadata
    metadata = FileMeta(
        file_id=file_id,
        file_name=uploaded_file.filename,
        uploaded_by=current_user
    )
    file_metadata_db[file_id] = metadata

    logger.info(f"File uploaded: {uploaded_file.filename} by {current_user}")

    return metadata


# ------------------------
# Delete file endpoint
# ------------------------
@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: str = Depends(get_current_user)
):
    if file_id not in file_metadata_db:
        raise HTTPException(status_code=404, detail="File not found")

    # Remove vectors from Qdrant
    vector_store.delete_document(file_id)

    # Remove metadata
    del file_metadata_db[file_id]

    # Invalidate cache (all cached answers containing this file)
    # For MVP, we can flush all FAQ cache or implement smarter invalidation later
    if cache.client:
        cache.client.flushdb()
        logger.info(f"Cache invalidated due to deletion of file {file_id}")

    logger.info(f"File deleted: {file_id} by {current_user}")

    return {"detail": f"File {file_id} deleted successfully"}


# ------------------------
# List files endpoint
# ------------------------
@router.get("/list", response_model=List[FileMeta])
async def list_files(current_user: str = Depends(get_current_user)):
    return list(file_metadata_db.values())
