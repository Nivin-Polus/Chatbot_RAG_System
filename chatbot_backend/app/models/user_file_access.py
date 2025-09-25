# app/models/user_file_access.py

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from pydantic import BaseModel
from typing import Optional, List
import uuid

class UserFileAccess(Base):
    """SQLAlchemy model for granular user file access control"""
    __tablename__ = "user_file_access"
    
    access_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    file_id = Column(String(36), ForeignKey("file_metadata.file_id"), nullable=False, index=True)
    
    # Permissions
    can_read = Column(Boolean, default=True, nullable=False)
    can_download = Column(Boolean, default=False, nullable=False)
    can_delete = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    granted_by = Column(String(36), ForeignKey("users.user_id"), nullable=False)  # Who granted this access
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional expiration
    notes = Column(Text, nullable=True)  # Optional notes about why access was granted
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="file_accesses")
    file = relationship("FileMetadata", back_populates="user_accesses")
    granter = relationship("User", foreign_keys=[granted_by])
    
    def to_dict(self):
        return {
            "access_id": self.access_id,
            "user_id": self.user_id,
            "file_id": self.file_id,
            "can_read": self.can_read,
            "can_download": self.can_download,
            "can_delete": self.can_delete,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "notes": self.notes
        }
    
    def is_expired(self) -> bool:
        """Check if this access has expired"""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if this access is currently valid"""
        return not self.is_expired()

# Pydantic models for API

class UserFileAccessCreate(BaseModel):
    """Pydantic model for creating file access"""
    user_id: str
    file_id: str
    can_read: bool = True
    can_download: bool = False
    can_delete: bool = False
    expires_at: Optional[str] = None  # ISO format datetime
    notes: Optional[str] = None

class UserFileAccessUpdate(BaseModel):
    """Pydantic model for updating file access"""
    can_read: Optional[bool] = None
    can_download: Optional[bool] = None
    can_delete: Optional[bool] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None

class UserFileAccessResponse(BaseModel):
    """Pydantic model for file access response"""
    access_id: str
    user_id: str
    file_id: str
    can_read: bool
    can_download: bool
    can_delete: bool
    granted_by: str
    granted_at: str
    expires_at: Optional[str] = None
    notes: Optional[str] = None

class UserFileAccessWithDetails(UserFileAccessResponse):
    """File access response with user and file details"""
    user_username: str
    user_full_name: Optional[str] = None
    file_name: str
    file_type: str
    granter_username: str

class BulkFileAccessCreate(BaseModel):
    """Pydantic model for bulk file access creation"""
    user_ids: List[str]
    file_ids: List[str]
    can_read: bool = True
    can_download: bool = False
    can_delete: bool = False
    expires_at: Optional[str] = None
    notes: Optional[str] = None

class FileAccessSummary(BaseModel):
    """Summary of file access for a user"""
    user_id: str
    username: str
    total_files: int
    readable_files: int
    downloadable_files: int
    deletable_files: int
    expired_accesses: int
