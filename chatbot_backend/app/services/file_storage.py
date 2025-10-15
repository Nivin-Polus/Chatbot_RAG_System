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
    def save_file(self, file: UploadFile, user_id: str, db: Session) -> FileMetadata:
        """Legacy method: Save uploaded file to default website"""
        from app.models.website import Website
        default_website = db.query(Website).first()
        website_id = default_website.website_id if default_website else None
        return self.save_file_with_website(
            user_id=user_id,
            website_id=website_id,
            db=db,
            file=file
        )
    
    def save_file_with_website(
        self,
        *,
        user_id: str,
        db: Session,
        website_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        file: Optional[UploadFile] = None,
        filename: Optional[str] = None,
        file_content: Optional[bytes] = None,
        save_to_disk: bool = False,
    ) -> FileMetadata:
        """
        Save uploaded file to DB and create metadata record.
        Keyword-only arguments required to avoid conflicts.
        """
        try:
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            original_filename: Optional[str] = None

            if file is not None:
                original_filename = file.filename
                if file_content is None:
                    file.file.seek(0)
                    file_content = file.file.read()
                if filename is None:
                    filename = original_filename
                mime_type = file.content_type or "application/octet-stream"
            else:
                mime_type = None

            if filename is None:
                raise HTTPException(status_code=400, detail="Filename is required for file upload")
            if file_content is None:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            if mime_type is None:
                guessed_type, _ = mimetypes.guess_type(filename)
                mime_type = guessed_type or "application/octet-stream"

            file_size = len(file_content)

            # Optional: save to disk
            if save_to_disk:
                storage_dir = settings.FILE_STORAGE_DIR or "/tmp/uploads"
                os.makedirs(storage_dir, exist_ok=True)
                disk_path = os.path.join(storage_dir, filename)
                with open(disk_path, "wb") as f:
                    f.write(file_content)
                logger.info(f"File saved to disk: {disk_path}")
            else:
                disk_path = None

            # Create metadata record
            file_metadata = FileMetadata(
                file_id=file_id,
                file_name=filename,
                file_path=disk_path,
                file_size=file_size,
                file_type=mime_type,
                website_id=website_id,
                uploader_id=user_id,
                collection_id=collection_id,
                processing_status="pending",
                chunk_count=0,
                upload_timestamp=datetime.utcnow(),
            )

            file_binary = FileBinary(
                file_id=file_id,
                data=file_content,
                mime_type=mime_type,
            )

            # Save to DB
            db.add(file_metadata)
            db.add(file_binary)
            db.commit()
            db.refresh(file_metadata)

            logger.info(
                f"File saved: {file_id} - {filename} ({file_size} bytes) "
                f"to website {website_id}, collection {collection_id}"
            )
            return file_metadata

        except Exception as e:
            logger.error(f"Failed to save file: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    def get_file_binary(self, file_id: str, db: Session) -> Optional[FileBinary]:
        """Retrieve file binary record by file ID"""
        return db.query(FileBinary).filter(FileBinary.file_id == file_id).first()
    
    def delete_file(self, file_id: str, db: Session) -> bool:
        """Delete file and associated metadata from database"""
        try:
            file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
            if not file_metadata:
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
    
    def update_processing_status(self, file_id: str, status: str, chunk_count: int, db: Session):
        """Update file processing status"""
        try:
            file_metadata = db.query(FileMetadata).filter(FileMetadata.file_id == file_id).first()
            if file_metadata:
                file_metadata.processing_status = status
                file_metadata.chunk_count = chunk_count
                db.commit()
                logger.info(f"File {file_id} status updated to {status} with {chunk_count} chunks")
        except Exception as e:
            logger.error(f"Failed to update file status: {str(e)}")
            db.rollback()
    
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
