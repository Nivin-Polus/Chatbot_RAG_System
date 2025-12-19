from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    collection_id = Column(String(50), ForeignKey("collections.collection_id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    session_name = Column(String(255), nullable=True)  # Optional session naming
    total_queries = Column(String(10), default="0")
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    queries = relationship("ChatQuery", back_populates="session", cascade="all, delete-orphan")
    message_history = relationship("ChatMessageHistory", back_populates="session", cascade="all, delete-orphan")
    collection = relationship("Collection", back_populates="chat_sessions")
    
    def to_dict(self):
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "session_name": self.session_name,
            "total_queries": self.total_queries,
            "collection_id": self.collection_id
        }

class ChatQuery(Base):
    __tablename__ = "chat_queries"
    
    query_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.session_id"), nullable=False)
    collection_id = Column(String(50), ForeignKey("collections.collection_id"), nullable=True, index=True)
    user_query = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    context_used = Column(JSON, nullable=True)  # Vector IDs, retrieved docs, etc.
    processing_time_ms = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship to session
    session = relationship("ChatSession", back_populates="queries")
    collection = relationship("Collection", back_populates="chat_queries")
    
    def to_dict(self):
        return {
            "query_id": self.query_id,
            "session_id": self.session_id,
            "user_query": self.user_query,
            "ai_response": self.ai_response,
            "context_used": self.context_used,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "collection_id": self.collection_id
        }


class ChatMessageHistory(Base):
    """Model for storing individual chat messages (user and assistant) with sources"""
    __tablename__ = "chat_message_history"
    
    message_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_message_id = Column(String(100), nullable=True, index=True)  # Original ID from frontend
    session_id = Column(String(36), ForeignKey("chat_sessions.session_id"), nullable=False, index=True)
    collection_id = Column(String(50), ForeignKey("collections.collection_id"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)  # Array of source objects with file_name, file_id, etc.
    message_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)  # Original timestamp from message
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)  # When saved to DB
    message_order = Column(Integer, nullable=True, index=True)  # Order in conversation (0, 1, 2, ...)
    
    # Relationships
    session = relationship("ChatSession", back_populates="message_history")
    collection = relationship("Collection", back_populates="message_history")
    
    def to_dict(self):
        return {
            "id": self.original_message_id or self.message_id,  # Return original ID if available
            "role": self.role,
            "content": self.content,
            "timestamp": self.message_timestamp.isoformat() if self.message_timestamp else (self.created_at.isoformat() if self.created_at else None),
            "sources": self.sources
        }


# Pydantic models for API
class ChatSessionCreate(BaseModel):
    """Pydantic model for chat session creation"""
    user_id: str
    session_name: Optional[str] = None


class ChatSessionResponse(BaseModel):
    """Pydantic model for chat session response"""
    session_id: str
    user_id: str
    created_at: str
    updated_at: Optional[str] = None
    session_name: Optional[str] = None
    total_queries: str


class ChatQueryCreate(BaseModel):
    """Pydantic model for chat query creation"""
    session_id: str
    user_query: str
    ai_response: str
    context_used: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[str] = None


class ChatQueryResponse(BaseModel):
    """Pydantic model for chat query response"""
    query_id: str
    session_id: str
    user_query: str
    ai_response: str
    context_used: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[str] = None
    created_at: str


# Pydantic models for ChatMessageHistory
class ChatMessageHistoryCreate(BaseModel):
    """Pydantic model for creating a chat message history entry"""
    session_id: str
    role: str  # 'user' or 'assistant'
    content: str
    sources: Optional[List[Dict[str, Any]]] = None


class ChatMessageHistoryResponse(BaseModel):
    """Pydantic model for chat message history response"""
    id: str
    role: str
    content: str
    timestamp: str
    sources: Optional[List[Dict[str, Any]]] = None


class ChatHistorySaveRequest(BaseModel):
    """Pydantic model for saving full chat history"""
    session_id: str
    collection_id: Optional[str] = None
    messages: List[Dict[str, Any]]  # List of message objects with id, role, content, timestamp, sources


class ChatHistoryResponse(BaseModel):
    """Pydantic model for retrieving chat history"""
    session_id: str
    messages: List[ChatMessageHistoryResponse]


# Alias for backward compatibility
ChatMessage = ChatQuery
ChatMessageCreate = ChatQueryCreate
