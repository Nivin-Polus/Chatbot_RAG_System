from typing import Optional
from fastapi import UploadFile, HTTPException
import mimetypes
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.file_metadata import FileMetadata
from app.models.file_binary import FileBinary
from app.config import settings
import uuid
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class FileStorageService:
    """Service for handling file storage operations"""
    
    def save_file_with_website(
        self,
        *,  # Force all parameters to be keyword-only
        user_id: str,
        website_id: str,
        db: Session,
        collection_id: Optional[str],
        filename: str,
        file_content: bytes,
    ) -> FileMetadata:
        """
        Save a file with website and user context
        
        Args:
            user_id: ID of the user uploading the file
            website_id: ID of the website the file belongs to
            db: Database session
            collection_id: Optional collection ID
            filename: Name of the file
            file_content: Binary content of the file
            
        Returns:
            FileMetadata: The created file metadata record
        """
        try:
            file_id = str(uuid.uuid4())  # Fixed: uuid4() -> uuid.uuid4()
            file_size = len(file_content)
            
            # Determine MIME type
            mime_type = self._get_mime_type(filename)
            
            # Create file metadata record
            file_metadata = FileMetadata(
                file_id=file_id,
                file_name=filename,
                file_size=file_size,
                file_type=mime_type,
                uploader_id=user_id,
                website_id=website_id,
                collection_id=collection_id,
                upload_timestamp=datetime.utcnow(),
                processing_status="processing",
                chunk_count=0,
            )
            
            # Create file binary record
            file_binary = FileBinary(
                file_id=file_id,
                data=file_content,
                mime_type=mime_type,
            )
            
            # Save to database
            db.add(file_metadata)
            db.add(file_binary)
            db.commit()
            db.refresh(file_metadata)
            
            logger.info(f"[FILE STORAGE] Saved file {file_id} ({filename}) for user {user_id}, website {website_id}")
            
            return file_metadata
            
        except Exception as e:
            db.rollback()
            logger.error(f"[FILE STORAGE ERROR] Failed to save file {filename}: {e}")
            raise
    
    def _get_mime_type(self, filename: str) -> str:
        """Determine MIME type from file extension"""
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        
        mime_types = {
            "pdf": "application/pdf",
            "txt": "text/plain",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "json": "application/json",
            "xml": "application/xml",
            "html": "text/html",
            "md": "text/markdown",
        }
        
        return mime_types.get(ext, "application/octet-stream")
    
    def update_processing_status(
        self,
        file_id: str,
        status: str,
        chunk_count: int,
        db: Session
    ) -> bool:
        """Update the processing status of a file"""
        try:
            file_record = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
            if file_record:
                file_record.processing_status = status
                file_record.chunk_count = chunk_count
                db.commit()
                logger.info(f"[FILE STORAGE] Updated status for {file_id}: {status}, chunks: {chunk_count}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"[FILE STORAGE ERROR] Failed to update status for {file_id}: {e}")
            return False
    
    def delete_file(self, file_id: str, db: Session) -> bool:
        """Delete file and associated metadata from database"""
        try:
            file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
            if not file_metadata:
                logger.warning(f"File metadata not found for deletion: {file_id}")
                return False

            file_binary = db.query(FileBinary).filter(FileBinary.file_id == file_id).first()

            db.delete(file_metadata)
            if file_binary:
                db.delete(file_binary)
            db.commit()

            logger.info(f"File metadata deleted: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {str(e)}")
            db.rollback()
            return False
    
    def get_file_binary(self, file_id: str, db: Session) -> Optional[FileBinary]:
        """Retrieve file binary data"""
        try:
            return db.query(FileBinary).filter(FileBinary.file_id == file_id).first()
        except Exception as e:
            logger.error(f"[FILE STORAGE ERROR] Failed to retrieve binary for {file_id}: {e}")
            return None
    
    def get_collection_files(self, collection_id: str, db: Session) -> list:
        """Get all files in a specific collection"""
        return db.query(FileMetadata).filter(FileMetadata.collection_id == collection_id).all()
    
    def get_website_files(self, website_id: str, db: Session) -> list:
        """Get all files for a specific website"""
        files = db.query(FileMetadata).filter(FileMetadata.website_id == website_id).all()
        return [file.to_dict() for file in files]
    
    def get_storage_stats(self, db: Session) -> dict:
        """Get storage statistics"""
        try:
            total_files = db.query(FileMetadata).count()
            total_size = db.query(FileMetadata).with_entities(
                func.sum(FileMetadata.file_size)
            ).scalar() or 0
            
            file_types = db.query(
                FileMetadata.file_type,
                func.count(FileMetadata.file_id)
            ).group_by(FileMetadata.file_type).all()
            
            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": {file_type: count for file_type, count in file_types}
            }
        except Exception as e:
            logger.error(f"Failed to get storage stats: {str(e)}")
            return {"error": str(e)}