# app/models/user.py

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from pydantic import BaseModel
from typing import Optional, List
import uuid

class User(Base):
    """SQLAlchemy User model for multi-tenant collection-based system"""
    __tablename__ = "users"
    
    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Multi-tenant fields
    website_id = Column(String(36), ForeignKey("websites.website_id"), nullable=True, index=True)
    
    # User preferences and settings
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(String(50), default="user", nullable=False)
    plugin_token = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    website = relationship("Website", back_populates="users")
    uploaded_files = relationship("FileMetadata", back_populates="uploader")
    file_accesses = relationship("UserFileAccess", foreign_keys="UserFileAccess.user_id", back_populates="user")
    chat_sessions = relationship("ChatSession", foreign_keys="ChatSession.user_id", back_populates="user")
    query_logs = relationship("QueryLog", back_populates="user")
    activity_logs = relationship("ActivityLog", back_populates="user")
    
    # Collection relationships
    administered_collections = relationship("Collection", foreign_keys="Collection.admin_user_id", back_populates="admin")
    collections = relationship("CollectionUser", foreign_keys="CollectionUser.user_id", back_populates="user")
    
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "website_id": self.website_id,
            "role": self.role,
            "plugin_token": self.plugin_token,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "collection_ids": [membership.collection_id for membership in self.collections]
        }
    
    def is_super_admin(self) -> bool:
        """Check if user is a super admin"""
        return self.role == "super_admin"
    
    def is_user_admin(self) -> bool:
        """Check if user is a user admin"""
        return self.role == "user_admin"
    
    def is_regular_user(self) -> bool:
        """Check if user is a regular-level account (includes plugin users)"""
        return self.role in {"user", "plugin_user"}

    def is_plugin_user(self) -> bool:
        """Check if user is a plugin user"""
        return self.role == "plugin_user"
    
    def can_manage_website(self, website_id: str) -> bool:
        """Check if user can manage a specific website"""
        if self.is_super_admin():
            return True
        if self.is_user_admin() and self.website_id == website_id:
            return True
        return False
    
    def can_access_website(self, website_id: str) -> bool:
        """Check if user can access a specific website"""
        if self.is_super_admin():
            return True
        return self.website_id == website_id
    
    def get_accessible_collections(self, db_session) -> List[str]:
        """Get list of collection IDs this user can access"""
        if self.is_super_admin():
            # Super admin can access all collections
            from app.models.collection import Collection
            collections = db_session.query(Collection.collection_id).all()
            return [c[0] for c in collections]
        
        elif self.is_user_admin():
            # User admin can access collections they administer
            from app.models.collection import Collection
            collections = db_session.query(Collection.collection_id).filter(
                Collection.admin_user_id == self.user_id
            ).all()
            return [c[0] for c in collections]
        
        else:
            # Regular user can access collections they're assigned to
            from app.models.collection import CollectionUser
            collections = db_session.query(CollectionUser.collection_id).filter(
                CollectionUser.user_id == self.user_id
            ).all()
            return [c[0] for c in collections]
    
    def get_accessible_file_ids(self, db_session) -> List[str]:
        """Get list of file IDs this user can access"""
        from app.models.file_metadata import FileMetadata
        
        if self.is_super_admin():
            # Super admin can access all files
            files = db_session.query(FileMetadata.file_id).all()
            return [f[0] for f in files]
        
        elif self.is_user_admin():
            # User admin can access files in their website
            files = db_session.query(FileMetadata.file_id).filter(
                FileMetadata.website_id == self.website_id
            ).all()
            return [f[0] for f in files]
        
        else:
            # Regular user can access files they have explicit access to
            try:
                from app.models.user_file_access import UserFileAccess
                file_access_records = db_session.query(UserFileAccess.file_id).filter(
                    UserFileAccess.user_id == self.user_id,
                    UserFileAccess.can_read == True
                ).all()
                return [f[0] for f in file_access_records]
            except:
                # If UserFileAccess model doesn't exist, return empty list
                return []

class UserCreate(BaseModel):
    """Pydantic model for user creation"""
    username: str
    password: str
    collection_id: Optional[str] = None  # Backwards compatibility for single assignment
    collection_ids: Optional[List[str]] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    website_id: Optional[str] = None  # Optional; derived from collection when omitted
    role: str = "user"  # super_admin, user_admin, user

class UserUpdate(BaseModel):
    """Pydantic model for user updates"""
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None  # Only super_admin can change roles
    collection_id: Optional[str] = None  # Backwards compatibility for legacy clients
    collection_ids: Optional[List[str]] = None

class UserLogin(BaseModel):
    """Pydantic model for user login"""
    username: str
    password: str
    website_id: Optional[str] = None  # Optional for domain-based routing

class UserResponse(BaseModel):
    """Pydantic model for user response"""
    user_id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    website_id: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_login: Optional[str] = None
    collection_ids: List[str]
    plugin_token: Optional[str] = None

class UserWithPermissions(UserResponse):
    """User response with permission information"""
    accessible_file_ids: List[str] = []
    can_upload_files: bool
    can_manage_users: bool
    can_manage_website: bool
