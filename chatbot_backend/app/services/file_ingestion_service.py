import logging
import os
import tempfile
import traceback
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from app.core.vector_singleton import get_vector_store
from app.services.file_storage import FileStorageService
from app.services.crawler.document_extractor import extract_text_from_document
from app.services.crawler.chunker import TextChunker, ContentChunk
from app.models.file_metadata import FileMetadata
from app.models.user import User

logger = logging.getLogger("file_ingestion")

class FileIngestionService:
    """
    Service for ingesting uploaded files into the vector store.
    Uses the same extraction and chunking logic as the web crawler.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.file_storage = FileStorageService()
        try:
            self.vector_store = get_vector_store()
        except Exception as e:
            logger.warning(f"Vector store not available: {e}")
            self.vector_store = None

    def process_file_background(self, file_id: str, user_id: str):
        """
        Background task to process an uploaded file.
        
        Args:
            file_id: ID of the file to process
            user_id: ID of the user who uploaded the file
        """
        try:
            # We need a new DB session for the background task if the original one is closed
            # However, for simplicity using the passed DB session if it's still valid, 
            # or creating a new one would be better pattern. 
            # Ideally this service is instantiated with a session factory or we manage session in the task wrapper.
            # Here we assume self.db is valid (passed from BackgroundTasks usually shares request scope or we need SessionLocal)
            # To be safe for background tasks, we should assume the passed db might be closed.
            # let's try to use it, but catch detached instance errors.
            pass 
        except Exception:
            pass
            
        # ACTUALLY: Best practice for BackgroundTasks in FastAPI is to use a fresh session 
        # because the request session will be closed.
        from app.core.database import SessionLocal
        with SessionLocal() as db:
            self.db = db
            self._process_file_impl(file_id, user_id)

    def _process_file_impl(self, file_id: str, user_id: str):
        """Implementation of file processing logic."""
        logger.info(f"Starting ingestion for file {file_id}")
        
        # 1. Get file metadata and binary
        file_meta = self.db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
        if not file_meta:
            logger.error(f"File metadata not found for {file_id}")
            return

        file_binary = self.file_storage.get_file_binary(file_id, self.db)
        if not file_binary or not file_binary.data:
            logger.error(f"File binary not found for {file_id}")
            self._update_status(file_id, "failed", 0, "No file content found")
            return

        # 2. Save to temp file for extraction
        temp_path = None
        try:
            # Create temp file with correct extension
            ext = os.path.splitext(file_meta.file_name)[1]
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                if hasattr(file_binary.data, 'tobytes'):
                     tmp.write(file_binary.data.tobytes())
                else:
                     tmp.write(file_binary.data)
                temp_path = tmp.name

            # 3. Extract text using document_extractor (same as crawler)
            # We treat the file_name as the URL for extraction context
            extracted_data = extract_text_from_document(temp_path, url=file_meta.file_name)
            
            if not extracted_data or not extracted_data.get("raw_text"):
                logger.warning(f"No text extracted from file {file_id}")
                self._update_status(file_id, "completed", 0, "No extractable text found")
                return

            # 4. Chunk text
            # We use TextChunker. SemanticChunker requires complex config, 
            # TextChunker is robust enough for files and used by default in crawler engine fallback.
            chunker = TextChunker()
            
            # Prepare extraction dict for chunker
            # TextChunker.chunk_page expects:
            # { "raw_text": ..., "title": ..., "url": ..., "canonical_url": ... }
            content_dict = {
                "raw_text": extracted_data["raw_text"],
                "title": file_meta.file_name,
                "url": file_meta.file_name, # Use filename as synthetic URL
                "canonical_url": file_meta.file_name,
                "sections": extracted_data.get("sections", [])
            }
            
            chunks = chunker.chunk_page(
                extracted_content=content_dict,
                job_id=file_id, # Use file_id as job_id for tracing
                collection_id=file_meta.collection_id or "default",
                crawl_depth=0
            )
            
            # 5. Store chunks in Vector Store
            if self.vector_store:
                docs_to_add = []
                for i, chunk in enumerate(chunks):
                    # Enrich metadata
                    meta = chunk.to_vector_metadata()
                    # Add file-specific fields that might not be in standard chunk metadata
                    meta.update({
                        "file_id": file_id,
                        "file_name": file_meta.file_name,
                        "uploader_id": user_id,
                        "website_id": file_meta.website_id,
                        "source_type": "file"
                    })
                    
                    docs_to_add.append({
                        "text": chunk.text,
                        "metadata": meta
                    })
                
                if docs_to_add:
                    self.vector_store.add_documents_with_metadata(docs_to_add)
                    logger.info(f"Stored {len(docs_to_add)} chunks for file {file_id}")
            
            # 6. Update status
            self._update_status(file_id, "completed", len(chunks))
            
            # Log activity
            try:
                user = self.db.query(User).filter(User.user_id == user_id).first()
                username = user.username if user else "unknown"
                
                # We assume activity_tracker is available globally or imported
                from app.services.activity_tracker import activity_tracker
                activity_tracker.log_activity(
                    activity_type="file_processed",
                    user=username,
                    details={
                        "file_id": file_id,
                        "file_name": file_meta.file_name,
                        "chunk_count": len(chunks),
                        "status": "completed"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log activity: {e}")

        except Exception as e:
            logger.error(f"Error processing file {file_id}: {str(e)}")
            logger.error(traceback.format_exc())
            self._update_status(file_id, "failed", 0, str(e))
        finally:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_path}: {e}")

    def _update_status(self, file_id: str, status: str, chunk_count: int, error_msg: Optional[str] = None):
        """Update file processing status."""
        try:
            self.file_storage.update_processing_status(file_id, status, chunk_count, self.db)
            # We could also store error message in DB if there was a field for it
        except Exception as e:
            logger.error(f"Failed to update status for {file_id}: {e}")
