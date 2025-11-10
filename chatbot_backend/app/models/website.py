# app/models/website.py

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from pydantic import BaseModel
from typing import Optional, List
import uuid

class Website(Base):
    """SQLAlchemy Website/Department model for multi-tenant isolation"""
    __tablename__ = "websites"
    
    website_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), unique=True, nullable=True, index=True)  # Optional domain binding
    description = Column(Text, nullable=True)
    
    # Configuration
    is_active = Column(Boolean, default=True, nullable=False)
    max_users = Column(Integer, default=100, nullable=False)
    max_files = Column(Integer, default=1000, nullable=False)
    max_storage_mb = Column(Integer, default=10240, nullable=False)  # 10GB default
    
    # Branding/Customization
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#6366f1", nullable=False)  # Hex color
    secondary_color = Column(String(7), default="#8b5cf6", nullable=False)
    custom_css = Column(Text, nullable=True)
    
    # Contact/Admin info
    admin_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="website")
    files = relationship("FileMetadata", back_populates="website")
    query_logs = relationship("QueryLog", back_populates="website")
    vector_databases = relationship("VectorDatabase", back_populates="website")
    prompts = relationship("SystemPrompt", back_populates="website")
    collections = relationship("Collection", back_populates="website")
    
    def to_dict(self):
        return {
            "website_id": self.website_id,
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "is_active": self.is_active,
            "max_users": self.max_users,
            "max_files": self.max_files,
            "max_storage_mb": self.max_storage_mb,
            "logo_url": self.logo_url,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "admin_email": self.admin_email,
            "contact_phone": self.contact_phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_usage_stats(self, db_session):
        """Get current usage statistics for this website"""
        from app.models.user import User
        from app.models.file_metadata import FileMetadata
        
        user_count = db_session.query(User).filter(User.website_id == self.website_id).count()
        file_count = db_session.query(FileMetadata).filter(FileMetadata.website_id == self.website_id).count()
        
        # Calculate total storage used
        total_storage = db_session.query(func.sum(FileMetadata.file_size)).filter(
            FileMetadata.website_id == self.website_id
        ).scalar() or 0
        
        return {
            "users": {
                "current": user_count,
                "max": self.max_users,
                "percentage": (user_count / self.max_users * 100) if self.max_users > 0 else 0
            },
            "files": {
                "current": file_count,
                "max": self.max_files,
                "percentage": (file_count / self.max_files * 100) if self.max_files > 0 else 0
            },
            "storage": {
                "current_bytes": total_storage,
                "current_mb": round(total_storage / (1024 * 1024), 2),
                "max_mb": self.max_storage_mb,
                "percentage": (total_storage / (self.max_storage_mb * 1024 * 1024) * 100) if self.max_storage_mb > 0 else 0
            }
        }

# Pydantic models for API

class WebsiteCreate(BaseModel):
    """Pydantic model for website creation"""
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    max_users: int = 100
    max_files: int = 1000
    max_storage_mb: int = 10240
    logo_url: Optional[str] = None
    primary_color: str = "#6366f1"
    secondary_color: str = "#8b5cf6"
    admin_email: Optional[str] = None
    contact_phone: Optional[str] = None

class WebsiteUpdate(BaseModel):
    """Pydantic model for website updates"""
    name: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    max_users: Optional[int] = None
    max_files: Optional[int] = None
    max_storage_mb: Optional[int] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    custom_css: Optional[str] = None
    admin_email: Optional[str] = None
    contact_phone: Optional[str] = None

class WebsiteResponse(BaseModel):
    """Pydantic model for website response"""
    website_id: str
    name: str
    domain: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    max_users: int
    max_files: int
    max_storage_mb: int
    logo_url: Optional[str] = None
    primary_color: str
    secondary_color: str
    admin_email: Optional[str] = None
    contact_phone: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class WebsiteWithStats(WebsiteResponse):
    """Website response with usage statistics"""
    usage_stats: dict
