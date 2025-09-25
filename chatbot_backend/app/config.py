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
    
    # Database Configuration - MySQL Support
    DATABASE_TYPE: str = Field("mysql", env="DATABASE_TYPE")  # mysql, sqlite, postgresql
    DATABASE_HOST: str = Field("localhost", env="DATABASE_HOST")
    DATABASE_PORT: int = Field(3306, env="DATABASE_PORT")  # Default MySQL port
    DATABASE_NAME: str = Field("chatbot_rag", env="DATABASE_NAME")
    DATABASE_USER: str = Field("root", env="DATABASE_USER")
    DATABASE_PASSWORD: str = Field("", env="DATABASE_PASSWORD")
    DATABASE_CHARSET: str = Field("utf8mb4", env="DATABASE_CHARSET")
    DATABASE_COLLATION: str = Field("utf8mb4_unicode_ci", env="DATABASE_COLLATION")
    
    # Connection Pool Settings
    DATABASE_POOL_SIZE: int = Field(10, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(20, env="DATABASE_MAX_OVERFLOW")
    DATABASE_POOL_TIMEOUT: int = Field(30, env="DATABASE_POOL_TIMEOUT")
    DATABASE_POOL_RECYCLE: int = Field(3600, env="DATABASE_POOL_RECYCLE")  # 1 hour
    
    # SSL Configuration for MySQL
    DATABASE_SSL_DISABLED: bool = Field(False, env="DATABASE_SSL_DISABLED")
    DATABASE_SSL_CA: str = Field("", env="DATABASE_SSL_CA")
    DATABASE_SSL_CERT: str = Field("", env="DATABASE_SSL_CERT")
    DATABASE_SSL_KEY: str = Field("", env="DATABASE_SSL_KEY")
    
    # Legacy DATABASE_URL for backward compatibility
    DATABASE_URL: str = Field("", env="DATABASE_URL")
    
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
    ALLOWED_FILE_TYPES: str = Field("pdf,docx,pptx,xlsx,txt,csv", env="ALLOWED_FILE_TYPES")
    UPLOAD_DIR: str = Field("uploads", env="UPLOAD_DIR")
    
    # Server Settings (using SERVER_HOST and SERVER_PORT from .env)
    HOST: str = Field("0.0.0.0", env="HOST")  # Fallback if HOST is used
    PORT: int = Field(8000, env="PORT")  # Fallback if PORT is used
    DEBUG: bool = Field(False, env="DEBUG")
    RELOAD: bool = Field(False, env="RELOAD")  # Auto-reload in production
    
    # CORS Settings
    CORS_ORIGINS: str = Field("http://localhost:3000,http://127.0.0.1:3000,http://10.199.100.54:3000", env="CORS_ORIGINS")  # Comma-separated list
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
    
    @property
    def database_url(self) -> str:
        """Generate database URL based on configuration"""
        # If DATABASE_URL is explicitly set, use it
        if self.DATABASE_URL:
            return self.DATABASE_URL
            
        # Generate URL based on database type
        if self.DATABASE_TYPE.lower() == "mysql":
            # MySQL URL format: mysql+pymysql://user:password@host:port/database?charset=utf8mb4
            url = f"mysql+pymysql://{self.DATABASE_USER}"
            if self.DATABASE_PASSWORD:
                url += f":{self.DATABASE_PASSWORD}"
            url += f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            url += f"?charset={self.DATABASE_CHARSET}"
            
            # Add SSL parameters if configured
            if not self.DATABASE_SSL_DISABLED:
                if self.DATABASE_SSL_CA:
                    url += f"&ssl_ca={self.DATABASE_SSL_CA}"
                if self.DATABASE_SSL_CERT:
                    url += f"&ssl_cert={self.DATABASE_SSL_CERT}"
                if self.DATABASE_SSL_KEY:
                    url += f"&ssl_key={self.DATABASE_SSL_KEY}"
            else:
                url += "&ssl_disabled=true"
                
            return url
            
        elif self.DATABASE_TYPE.lower() == "postgresql":
            # PostgreSQL URL format
            url = f"postgresql://{self.DATABASE_USER}"
            if self.DATABASE_PASSWORD:
                url += f":{self.DATABASE_PASSWORD}"
            url += f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            return url
            
        elif self.DATABASE_TYPE.lower() == "sqlite":
            # SQLite URL format
            return f"sqlite:///./{self.DATABASE_NAME}.db"
            
        else:
            raise ValueError(f"Unsupported database type: {self.DATABASE_TYPE}")
    
    @property
    def database_connect_args(self) -> dict:
        """Get database connection arguments based on type"""
        if self.DATABASE_TYPE.lower() == "mysql":
            args = {}
            # Add SSL configuration if not disabled
            if not self.DATABASE_SSL_DISABLED:
                ssl_config = {}
                if self.DATABASE_SSL_CA:
                    ssl_config["ca"] = self.DATABASE_SSL_CA
                if self.DATABASE_SSL_CERT:
                    ssl_config["cert"] = self.DATABASE_SSL_CERT
                if self.DATABASE_SSL_KEY:
                    ssl_config["key"] = self.DATABASE_SSL_KEY
                if ssl_config:
                    args["ssl"] = ssl_config
            return args
            
        elif self.DATABASE_TYPE.lower() == "sqlite":
            return {"check_same_thread": False}
            
        else:
            return {}


# Instantiate settings
settings = Settings()
