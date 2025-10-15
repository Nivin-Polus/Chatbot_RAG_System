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

# Optional import to resolve user_id when legacy callers pass UploadFile instead of user_id
try:
	from app.models.user import User
except Exception:
	User = None

logger = logging.getLogger(__name__)

class FileStorageService:
	"""Service for handling file storage operations"""
	
	def save_file_with_website(
		self,
		*args,
		user_id: Optional[str] = None,
		website_id: Optional[str] = None,
		db: Optional[Session] = None,
		collection_id: Optional[str] = None,
		filename: Optional[str] = None,
		file_content: Optional[bytes] = None,
	) -> FileMetadata:
		"""
		Save a file with website and user context
		
		Backward-compatible with older positional-argument call sites. Supported
		positional order: (user_id, website_id, db, collection_id, filename, file_content)
		Legacy variant: (uploaded_file: UploadFile, website_id, db, collection_id, user_id, file_content?)
		
		Args:
			user_id: ID of the user uploading the file
			website_id: ID of the website the file belongs to (optional)
			db: Database session
			collection_id: Optional collection ID
			filename: Name of the file
			file_content: Binary content of the file
		
		Returns:
			FileMetadata: The created file metadata record
		"""
		# Legacy mapping when first arg is an UploadFile
		if args and isinstance(args[0], UploadFile):
			legacy = list(args)
			uploaded_file: UploadFile = legacy[0]
			if website_id is None and len(legacy) > 1:
				website_id = legacy[1]
			if db is None and len(legacy) > 2:
				db = legacy[2]
			if collection_id is None and len(legacy) > 3:
				collection_id = legacy[3]
			if user_id is None and len(legacy) > 4:
				user_id = legacy[4]
			# filename from UploadFile if not provided
			if filename is None:
				try:
					filename = uploaded_file.filename
				except Exception:
					filename = None
			# file_content: prefer explicit arg if provided; otherwise attempt to read
			if file_content is None:
				try:
					if len(legacy) > 5 and isinstance(legacy[5], (bytes, bytearray)):
						file_content = legacy[5]
					else:
						# Try to read from file-like object without assuming async
						if hasattr(uploaded_file, "file") and hasattr(uploaded_file.file, "read"):
							try:
								uploaded_file.file.seek(0)
							except Exception:
								pass
							file_content = uploaded_file.file.read()
				except Exception:
					file_content = None
		elif args:
			# Default positional mapping: (user_id, website_id, db, collection_id, filename, file_content)
			ordered = list(args) + [None] * (6 - len(args))
			if user_id is None:
				user_id = ordered[0]
			if website_id is None:
				website_id = ordered[1]
			if db is None:
				db = ordered[2]
			if collection_id is None:
				collection_id = ordered[3]
			if filename is None:
				filename = ordered[4]
			if file_content is None:
				file_content = ordered[5]
		
		# If user_id was incorrectly passed as an UploadFile via keyword, fix it
		if isinstance(user_id, UploadFile):
			uploaded_file_kw: UploadFile = user_id
			# derive filename and content if still missing
			if filename is None:
				try:
					filename = uploaded_file_kw.filename
				except Exception:
					pass
			if file_content is None and hasattr(uploaded_file_kw, "file") and hasattr(uploaded_file_kw.file, "read"):
				try:
					uploaded_file_kw.file.seek(0)
				except Exception:
					pass
				try:
					file_content = uploaded_file_kw.file.read()
				except Exception:
					pass
			# try to resolve a real user_id from DB if available
			if db is not None and isinstance(website_id, str) and User is not None:
				try:
					candidate = db.query(User).filter(User.website_id == website_id).order_by(User.created_at.desc()).first()
					if candidate and getattr(candidate, "user_id", None):
						user_id = candidate.user_id
				except Exception:
					pass
		
		# Log received parameters for diagnostics
		try:
			logger.info(
				"[FILE STORAGE] save_file_with_website params | user_id=%r website_id=%r db_set=%s collection_id=%r filename=%r content_len=%s",
				user_id,
				website_id,
				bool(db),
				collection_id,
				filename,
				(None if file_content is None else len(file_content)),
			)
		except Exception:
			pass
		
		# Basic validation (website_id is optional per DB model)
		if not user_id or db is None or not filename or file_content is None:
			raise HTTPException(status_code=400, detail="Missing required parameters for save_file_with_website")
		
		try:
			file_id = str(uuid.uuid4())
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
				website_id=website_id,  # optional
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