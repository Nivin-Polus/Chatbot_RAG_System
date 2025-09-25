# app/models/system_prompt.py

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Float, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base
from pydantic import BaseModel
from typing import Optional, List
import uuid

class SystemPrompt(Base):
    """SQLAlchemy SystemPrompt model for database-driven prompts"""
    __tablename__ = "system_prompts"
    
    prompt_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Prompt content
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=True)  # Template for user prompts
    context_template = Column(Text, nullable=True)  # Template for context injection
    
    # Association
    vector_db_id = Column(String(36), ForeignKey("vector_databases.vector_db_id"), nullable=True, index=True)
    website_id = Column(String(36), ForeignKey("websites.website_id"), nullable=True, index=True)
    collection_id = Column(String(50), ForeignKey("collections.collection_id"), nullable=True, index=True)
    
    # Configuration
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)  # Default prompt for the vector DB
    
    # AI Model Configuration
    model_name = Column(String(100), default="claude-3-haiku-20240307", nullable=False)
    max_tokens = Column(Integer, default=1000, nullable=False)
    temperature = Column(Float, default=0.0, nullable=False)
    
    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_used = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    vector_database = relationship("VectorDatabase", back_populates="prompts")
    website = relationship("Website", back_populates="prompts")
    collection = relationship("Collection", back_populates="prompts")
    
    def to_dict(self):
        return {
            "prompt_id": self.prompt_id,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "context_template": self.context_template,
            "vector_db_id": self.vector_db_id,
            "website_id": self.website_id,
            "collection_id": self.collection_id,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "collection_name": self.collection.name if self.collection else None,
            "vector_db_name": self.vector_database.name if self.vector_database else None,
            "website_name": self.website.name if self.website else None
        }
    
    def format_prompt(self, user_query: str, context: str = "") -> dict:
        """Format the prompt with user query and context"""
        # Use templates if available, otherwise use defaults
        if self.user_prompt_template:
            formatted_user_prompt = self.user_prompt_template.format(
                query=user_query,
                context=context
            )
        else:
            formatted_user_prompt = f"User Query: {user_query}\n\nContext: {context}"
        
        return {
            "system_prompt": self.system_prompt,
            "user_prompt": formatted_user_prompt,
            "model_config": {
                "model": self.model_name,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
        }
    
    def increment_usage(self, db_session):
        """Increment usage count and update last used timestamp"""
        self.usage_count += 1
        self.last_used = func.now()
        db_session.commit()

# Pydantic models for API

class SystemPromptCreate(BaseModel):
    """Pydantic model for system prompt creation"""
    name: str
    description: Optional[str] = None
    system_prompt: str
    user_prompt_template: Optional[str] = None
    context_template: Optional[str] = None
    vector_db_id: Optional[str] = None
    collection_id: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    model_name: str = "claude-3-haiku-20240307"
    max_tokens: int = 1000
    temperature: float = 0.0

class SystemPromptUpdate(BaseModel):
    """Pydantic model for system prompt updates"""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    context_template: Optional[str] = None
    collection_id: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

class SystemPromptResponse(BaseModel):
    """Pydantic model for system prompt response"""
    prompt_id: str
    name: str
    description: Optional[str] = None
    system_prompt: str
    user_prompt_template: Optional[str] = None
    context_template: Optional[str] = None
    vector_db_id: Optional[str] = None
    website_id: Optional[str] = None
    collection_id: Optional[str] = None
    is_active: bool
    is_default: bool
    model_name: str
    max_tokens: int
    temperature: float
    usage_count: int
    created_at: str
    updated_at: str
    last_used: Optional[str] = None
    collection_name: Optional[str] = None
    vector_db_name: Optional[str] = None
    website_name: Optional[str] = None

class SystemPromptWithDetails(SystemPromptResponse):
    """System prompt response with additional details"""
    vector_db_name: Optional[str] = None
    website_name: Optional[str] = None
