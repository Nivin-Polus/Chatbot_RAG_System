"""
Collection model for the collection-based RAG system.
Each collection represents a logical division of the vector database.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Collection(Base):
    """
    Collection model representing a logical division of the vector database.
    Each collection has a unique ID, admin, users, and custom prompts.
    """
    __tablename__ = "collections"

    collection_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    website_id = Column(String(36), ForeignKey("websites.website_id"), nullable=True, index=True)
    vector_db_id = Column(String(36), ForeignKey("vector_databases.vector_db_id"), nullable=True, index=True)
    website_url = Column(String(500))
    
    # Admin assignment
    admin_user_id = Column(String(36), ForeignKey("users.user_id"))
    admin_email = Column(String(255))
    
    # Status and metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    admin = relationship("User", foreign_keys=[admin_user_id], back_populates="administered_collections")
    website = relationship("Website", back_populates="collections")
    vector_db = relationship("VectorDatabase", back_populates="collections")
    users = relationship("CollectionUser", back_populates="collection")
    prompts = relationship("SystemPrompt", back_populates="collection")
    files = relationship("FileMetadata", back_populates="collection")
    chat_sessions = relationship("ChatSession", back_populates="collection")
    chat_queries = relationship("ChatQuery", back_populates="collection")
    
    def __repr__(self):
        return f"<Collection(id='{self.collection_id}', name='{self.name}')>"

    @property
    def user_count(self):
        """Get the number of users in this collection"""
        return len(self.users) if self.users else 0
    
    @property
    def prompt_count(self):
        """Get the number of prompts in this collection"""
        return len(self.prompts) if self.prompts else 0
    
    @property
    def file_count(self):
        """Get the number of files in this collection"""
        # Since files relationship is disabled, return 0 for now
        return 0


class CollectionUser(Base):
    """
    Association table for users assigned to collections.
    Manages the many-to-many relationship between users and collections.
    """
    __tablename__ = "collection_users"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(String(50), ForeignKey("collections.collection_id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    role = Column(String(50), default="user")  # admin, user
    
    # Permissions
    can_upload = Column(Boolean, default=True)
    can_download = Column(Boolean, default=True)
    can_delete = Column(Boolean, default=False)
    
    # Metadata
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(String(36), ForeignKey("users.user_id"))
    
    # Relationships
    collection = relationship("Collection", back_populates="users")
    user = relationship("User", foreign_keys=[user_id], back_populates="collections")
    assigner = relationship("User", foreign_keys=[assigned_by])
    
    def __repr__(self):
        return f"<CollectionUser(collection='{self.collection_id}', user='{self.user_id}', role='{self.role}')>"
