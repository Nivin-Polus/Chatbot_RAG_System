# app/models/query_log.py

from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import json

class QueryLog(Base):
    """SQLAlchemy model for tracking user queries and system usage"""
    __tablename__ = "query_logs"
    
    query_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # User and website context
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    website_id = Column(String(36), ForeignKey("websites.website_id"), nullable=False, index=True)
    session_id = Column(String(36), nullable=True, index=True)  # Chat session ID
    
    # Query details
    user_query = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=True)
    query_type = Column(String(50), default="chat", nullable=False)  # chat, search, upload, etc.
    
    # Performance metrics
    processing_time_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    chunks_retrieved = Column(Integer, nullable=True)
    
    # Context and metadata
    context_used = Column(Text, nullable=True)  # JSON string of context
    files_accessed = Column(Text, nullable=True)  # JSON array of file IDs
    vector_search_score = Column(Float, nullable=True)
    
    # Status and error tracking
    status = Column(String(20), default="success", nullable=False)  # success, error, timeout
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="query_logs")
    website = relationship("Website", back_populates="query_logs")
    
    def to_dict(self):
        return {
            "query_id": self.query_id,
            "user_id": self.user_id,
            "website_id": self.website_id,
            "session_id": self.session_id,
            "user_query": self.user_query,
            "ai_response": self.ai_response,
            "query_type": self.query_type,
            "processing_time_ms": self.processing_time_ms,
            "tokens_used": self.tokens_used,
            "chunks_retrieved": self.chunks_retrieved,
            "context_used": self.context_used,
            "files_accessed": self.files_accessed,
            "vector_search_score": self.vector_search_score,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def get_context_data(self) -> Dict[str, Any]:
        """Parse context_used JSON string"""
        if not self.context_used:
            return {}
        try:
            return json.loads(self.context_used)
        except json.JSONDecodeError:
            return {}
    
    def set_context_data(self, context: Dict[str, Any]):
        """Set context_used as JSON string"""
        self.context_used = json.dumps(context) if context else None
    
    def get_files_accessed_list(self) -> List[str]:
        """Parse files_accessed JSON array"""
        if not self.files_accessed:
            return []
        try:
            return json.loads(self.files_accessed)
        except json.JSONDecodeError:
            return []
    
    def set_files_accessed_list(self, file_ids: List[str]):
        """Set files_accessed as JSON array"""
        self.files_accessed = json.dumps(file_ids) if file_ids else None

# Pydantic models for API

class QueryLogCreate(BaseModel):
    """Pydantic model for creating query logs"""
    user_id: str
    website_id: str
    session_id: Optional[str] = None
    user_query: str
    ai_response: Optional[str] = None
    query_type: str = "chat"
    processing_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    chunks_retrieved: Optional[int] = None
    context_data: Optional[Dict[str, Any]] = None
    files_accessed: Optional[List[str]] = None
    vector_search_score: Optional[float] = None
    status: str = "success"
    error_message: Optional[str] = None

class QueryLogResponse(BaseModel):
    """Pydantic model for query log response"""
    query_id: str
    user_id: str
    website_id: str
    session_id: Optional[str] = None
    user_query: str
    ai_response: Optional[str] = None
    query_type: str
    processing_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    chunks_retrieved: Optional[int] = None
    vector_search_score: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    created_at: str

class QueryLogWithDetails(QueryLogResponse):
    """Query log with user and website details"""
    username: str
    website_name: str
    context_data: Optional[Dict[str, Any]] = None
    files_accessed: Optional[List[str]] = None

class QueryAnalytics(BaseModel):
    """Analytics summary for queries"""
    total_queries: int
    successful_queries: int
    failed_queries: int
    avg_processing_time_ms: Optional[float] = None
    total_tokens_used: Optional[int] = None
    most_active_users: List[Dict[str, Any]]
    query_types_breakdown: Dict[str, int]
    hourly_distribution: Dict[str, int]
    daily_distribution: Dict[str, int]

class UserQueryStats(BaseModel):
    """Query statistics for a specific user"""
    user_id: str
    username: str
    total_queries: int
    successful_queries: int
    failed_queries: int
    avg_processing_time_ms: Optional[float] = None
    total_tokens_used: Optional[int] = None
    most_recent_query: Optional[str] = None
    favorite_query_types: Dict[str, int]

class WebsiteQueryStats(BaseModel):
    """Query statistics for a specific website"""
    website_id: str
    website_name: str
    total_queries: int
    unique_users: int
    avg_queries_per_user: float
    most_active_hours: List[int]
    top_query_types: Dict[str, int]
    performance_metrics: Dict[str, float]
