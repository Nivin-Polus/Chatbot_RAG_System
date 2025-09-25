# app/models/vector_database.py

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from pydantic import BaseModel
from typing import Optional, List
import uuid

class VectorDatabase(Base):
    """SQLAlchemy VectorDatabase model for managing vector collections with unique IDs"""
    __tablename__ = "vector_databases"
    
    vector_db_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Multi-tenant association
    website_id = Column(String(36), ForeignKey("websites.website_id"), nullable=True, index=True)
    
    # Vector DB Configuration
    collection_name = Column(String(255), nullable=False, unique=True)  # Qdrant collection name
    web_link = Column(String(500), nullable=True)  # Optional web link for data source
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    document_count = Column(Integer, default=0, nullable=False)
    total_chunks = Column(Integer, default=0, nullable=False)
    size_mb = Column(Integer, default=0, nullable=False)
    
    # Configuration
    embedding_model = Column(String(100), default="sentence-transformers/all-MiniLM-L6-v2", nullable=False)
    chunk_size = Column(Integer, default=1000, nullable=False)
    chunk_overlap = Column(Integer, default=200, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_accessed = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    website = relationship("Website", back_populates="vector_databases")
    prompts = relationship("SystemPrompt", back_populates="vector_database")
    collections = relationship("Collection", back_populates="vector_db")
    # files = relationship("FileMetadata", foreign_keys="FileMetadata.vector_db_id", back_populates="vector_database")  # Commented out - column doesn't exist
    
    def to_dict(self):
        return {
            "vector_db_id": self.vector_db_id,
            "name": self.name,
            "description": self.description,
            "website_id": self.website_id,
            "collection_name": self.collection_name,
            "web_link": self.web_link,
            "is_active": self.is_active,
            "document_count": self.document_count,
            "total_chunks": self.total_chunks,
            "size_mb": self.size_mb,
            "embedding_model": self.embedding_model,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None
        }
    
    def get_stats(self, db_session):
        """Get detailed statistics for this vector database"""
        # Since vector_db_id relationship is disabled, return basic stats
        return {
            "vector_db_id": self.vector_db_id,
            "name": self.name,
            "collection_name": self.collection_name,
            "total_files": 0,  # Would need alternative query method
            "indexed_files": 0,
            "indexing_progress": 0,
            "total_size_bytes": 0,
            "total_size_mb": 0,
            "document_count": self.document_count,
            "total_chunks": self.total_chunks,
            "is_active": self.is_active,
            "web_link": self.web_link
        }

# Pydantic models for API

class VectorDatabaseCreate(BaseModel):
    """Pydantic model for vector database creation"""
    name: str
    description: Optional[str] = None
    website_id: Optional[str] = None
    web_link: Optional[str] = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200

class VectorDatabaseUpdate(BaseModel):
    """Pydantic model for vector database updates"""
    name: Optional[str] = None
    description: Optional[str] = None
    web_link: Optional[str] = None
    is_active: Optional[bool] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None

class VectorDatabaseResponse(BaseModel):
    """Pydantic model for vector database response"""
    vector_db_id: str
    name: str
    description: Optional[str] = None
    website_id: str
    collection_name: str
    web_link: Optional[str] = None
    is_active: bool
    document_count: int
    total_chunks: int
    size_mb: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    created_at: str
    updated_at: str
    last_accessed: Optional[str] = None

class VectorDatabaseWithStats(VectorDatabaseResponse):
    """Vector database response with detailed statistics"""
    stats: dict
    website_name: str
    prompt_count: int
