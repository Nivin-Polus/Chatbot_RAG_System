# app/config.py

import os
from dotenv import load_dotenv
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field

# Load .env file
load_dotenv()


class Settings(BaseSettings):
    # Claude API
    CLAUDE_API_KEY: str = Field(default="", env="CLAUDE_API_KEY")
    CLAUDE_API_URL: str = Field("https://api.anthropic.com/v1/messages", env="CLAUDE_API_URL")
    CLAUDE_MODEL: str = Field("claude-3-haiku-20240307", env="CLAUDE_MODEL")
    CLAUDE_MAX_TOKENS: int = Field(1000, env="CLAUDE_MAX_TOKENS")
    CLAUDE_TEMPERATURE: float = Field(0.0, env="CLAUDE_TEMPERATURE")
    SYSTEM_PROMPT: str = Field("", env="SYSTEM_PROMPT")  # Empty means use default
    
    # Server Configuration (from your .env)
    SERVER_HOST: str = Field("0.0.0.0", env="SERVER_HOST")
    SERVER_PORT: int = Field(8000, env="SERVER_PORT")
    
    # Frontend Configuration (from your .env)
    FRONTEND_HOST: str = Field("localhost", env="FRONTEND_HOST")
    FRONTEND_PORT: int = Field(3000, env="FRONTEND_PORT")
    
    # Database Configuration (from your .env)
    DATABASE_URL: str = Field("sqlite:///./chatbot.db", env="DATABASE_URL")
    DATABASE_HOST: str = Field("localhost", env="DATABASE_HOST")
    DATABASE_PORT: int = Field(5432, env="DATABASE_PORT")
    
    # Vector DB (Qdrant) - with fallback support
    VECTOR_DB_URL: str = Field("http://localhost:6333", env="VECTOR_DB_URL")
    VECTOR_DB_FALLBACK: bool = Field(True, env="VECTOR_DB_FALLBACK")  # Enable fallback mode
    
    # Redis (optional)
    USE_REDIS: bool = Field(False, env="USE_REDIS")
    REDIS_HOST: str = Field("localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_DB: int = Field(0, env="REDIS_DB")
    REDIS_TIMEOUT: int = Field(5, env="REDIS_TIMEOUT")  # Connection timeout in seconds
    
    # JWT Auth
    SECRET_KEY: str = Field(default="", env="SECRET_KEY")
    ALGORITHM: str = Field("HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # App mode
    APP_MODE: str = Field("api", env="APP_MODE")  # "api" or "ui"
    
    # File settings
    MAX_FILE_SIZE_MB: int = Field(25, env="MAX_FILE_SIZE_MB")
    ALLOWED_FILE_TYPES: str = Field("pdf,docx,pptx,xlsx,txt", env="ALLOWED_FILE_TYPES")
    UPLOAD_DIR: str = Field("uploads", env="UPLOAD_DIR")
    
    # Server Settings (using SERVER_HOST and SERVER_PORT from .env)
    HOST: str = Field("0.0.0.0", env="HOST")  # Fallback if HOST is used
    PORT: int = Field(8000, env="PORT")  # Fallback if PORT is used
    DEBUG: bool = Field(False, env="DEBUG")
    RELOAD: bool = Field(False, env="RELOAD")  # Auto-reload in production
    
    # CORS Settings
    CORS_ORIGINS: str = Field("*", env="CORS_ORIGINS")  # Comma-separated list
    CORS_METHODS: str = Field("*", env="CORS_METHODS")
    CORS_HEADERS: str = Field("*", env="CORS_HEADERS")
    
    # Activity Tracking
    ACTIVITY_LOG_DIR: str = Field("activity_logs", env="ACTIVITY_LOG_DIR")
    ACTIVITY_RETENTION_DAYS: int = Field(30, env="ACTIVITY_RETENTION_DAYS")

    # API credentials
    API_USERNAME: str = Field("your_username", env="API_USERNAME")
    API_PASSWORD_HASH: str = Field("your_hashed_password", env="API_PASSWORD_HASH")

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in .env file
        
    @property
    def effective_host(self) -> str:
        """Get the effective host (prefer SERVER_HOST over HOST)"""
        return self.SERVER_HOST or self.HOST
        
    @property
    def effective_port(self) -> int:
        """Get the effective port (prefer SERVER_PORT over PORT)"""
        return self.SERVER_PORT or self.PORT


# Instantiate settings
settings = Settings()
