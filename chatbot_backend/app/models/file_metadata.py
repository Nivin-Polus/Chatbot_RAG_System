from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from pydantic import BaseModel
from typing import Optional, List
import uuid

class FileMetadata(Base):
    __tablename__ = "file_metadata"
    
    file_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False)
    
    # Multi-tenant fields
    website_id = Column(String(36), ForeignKey("websites.website_id"), nullable=True, index=True)
    uploader_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    collection_id = Column(String(50), ForeignKey("collections.collection_id"), nullable=True, index=True)
    
    # File metadata
    upload_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    processing_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    chunk_count = Column(Integer, default=0)
    
    # Additional metadata
    description = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)  # Comma-separated tags
    is_public = Column(Boolean, default=False, nullable=False)  # Public within website
    mime_type = Column(String(100), nullable=True)
    # Vector DB metadata
    vector_collection = Column(String(100), nullable=True)  # Qdrant collection name
    vector_indexed = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    website = relationship("Website", back_populates="files")
    uploader = relationship("User", back_populates="uploaded_files")
    collection = relationship("Collection", back_populates="files")
    user_accesses = relationship("UserFileAccess", foreign_keys="UserFileAccess.file_id", back_populates="file")
    
    def to_dict(self):
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "website_id": self.website_id,
            "uploader_id": self.uploader_id,
            "collection_id": self.collection_id,
            "upload_timestamp": self.upload_timestamp.isoformat() if self.upload_timestamp else None,
            "processing_status": self.processing_status,
            "chunk_count": self.chunk_count,
            "description": self.description,
            "tags": self.tags,
            "is_public": self.is_public,
            "mime_type": self.mime_type,
            "vector_collection": self.vector_collection,
            "vector_indexed": self.vector_indexed
        }
    
    def get_tags_list(self) -> List[str]:
        """Get tags as a list"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
    
    def set_tags_list(self, tags: List[str]):
        """Set tags from a list"""
        self.tags = ",".join(tags) if tags else None
    
    def get_vector_metadata(self) -> dict:
        """Get metadata for vector storage"""
        return {
            "website_id": self.website_id,
            "file_id": self.file_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "uploader_id": self.uploader_id,
            "tags": self.get_tags_list(),
            "is_public": self.is_public
        }

# Pydantic models for API

class FileMetadataCreate(BaseModel):
    """Pydantic model for file metadata creation"""
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    website_id: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: bool = False
    mime_type: Optional[str] = None

class FileMetadataUpdate(BaseModel):
    """Pydantic model for file metadata updates"""
    file_name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    processing_status: Optional[str] = None

class FileMetadataResponse(BaseModel):
    """Pydantic model for file metadata response"""
    file_id: str
    file_name: str
    file_size: int
    file_type: str
    website_id: str
    uploader_id: str
    upload_timestamp: str
    processing_status: str
    chunk_count: int
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: bool
    mime_type: Optional[str] = None
    vector_indexed: bool

class FileMetadataWithAccess(FileMetadataResponse):
    """File metadata with user access information"""
    can_read: bool
    can_download: bool
    can_delete: bool
    uploader_username: str
    website_name: str
