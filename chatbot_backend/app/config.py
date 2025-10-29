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
    CLAUDE_API_KEY: str = Field(default="", validation_alias="CLAUDE_API_KEY")
    CLAUDE_API_URL: str = Field("https://api.anthropic.com/v1/messages", validation_alias="CLAUDE_API_URL")
    CLAUDE_MODEL: str = Field("claude-3-haiku-20240307", validation_alias="CLAUDE_MODEL")
    CLAUDE_MAX_TOKENS: int = Field(1000, validation_alias="CLAUDE_MAX_TOKENS")
    CLAUDE_TEMPERATURE: float = Field(0.0, validation_alias="CLAUDE_TEMPERATURE")
    SYSTEM_PROMPT: str = Field("", validation_alias="SYSTEM_PROMPT")  # Empty means use default
    
    # AWS Bedrock Configuration
    AWS_REGION: str = Field("us-east-1", validation_alias="AWS_REGION")
    AWS_ACCESS_KEY_ID: str = Field("", validation_alias="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = Field("", validation_alias="AWS_SECRET_ACCESS_KEY")
    AWS_MODEL: str = Field("anthropic.claude-3-5-sonnet-20241022-v1:0", validation_alias="AWS_MODEL")
    
    # Server Configuration (from your .env)
    SERVER_HOST: str = Field("0.0.0.0", validation_alias="SERVER_HOST")
    SERVER_PORT: int = Field(8000, validation_alias="SERVER_PORT")
    
    # Frontend Configuration (from your .env)
    FRONTEND_HOST: str = Field("localhost", validation_alias="FRONTEND_HOST")
    FRONTEND_PORT: int = Field(3000, validation_alias="FRONTEND_PORT")
    
    # Database Configuration - MySQL Support
    DATABASE_TYPE: str = Field("mysql", validation_alias="DATABASE_TYPE")  # mysql, sqlite, postgresql
    DATABASE_HOST: str = Field("localhost", validation_alias="DATABASE_HOST")
    DATABASE_PORT: int = Field(3306, validation_alias="DATABASE_PORT")  # Default MySQL port
    DATABASE_NAME: str = Field("chatbot_rag", validation_alias="DATABASE_NAME")
    DATABASE_USER: str = Field("root", validation_alias="DATABASE_USER")
    DATABASE_PASSWORD: str = Field("", validation_alias="DATABASE_PASSWORD")
    DATABASE_CHARSET: str = Field("utf8mb4", validation_alias="DATABASE_CHARSET")
    DATABASE_COLLATION: str = Field("utf8mb4_unicode_ci", validation_alias="DATABASE_COLLATION")
    
    # Connection Pool Settings
    DATABASE_POOL_SIZE: int = Field(10, validation_alias="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(20, validation_alias="DATABASE_MAX_OVERFLOW")
    DATABASE_POOL_TIMEOUT: int = Field(30, validation_alias="DATABASE_POOL_TIMEOUT")
    DATABASE_POOL_RECYCLE: int = Field(3600, validation_alias="DATABASE_POOL_RECYCLE")  # 1 hour
    
    # SSL Configuration for MySQL
    DATABASE_SSL_DISABLED: bool = Field(False, validation_alias="DATABASE_SSL_DISABLED")
    DATABASE_SSL_CA: str = Field("", validation_alias="DATABASE_SSL_CA")
    DATABASE_SSL_CERT: str = Field("", validation_alias="DATABASE_SSL_CERT")
    DATABASE_SSL_KEY: str = Field("", validation_alias="DATABASE_SSL_KEY")
    
    # Legacy DATABASE_URL for backward compatibility
    DATABASE_URL: str = Field("", validation_alias="DATABASE_URL")
    
    # Vector DB (Qdrant) - with fallback support
    VECTOR_DB_URL: str = Field("http://localhost:6333", validation_alias="VECTOR_DB_URL")
    VECTOR_DB_FALLBACK: bool = Field(True, validation_alias="VECTOR_DB_FALLBACK")  # Enable fallback mode
    
    # Redis (optional)
    USE_REDIS: bool = Field(False, validation_alias="USE_REDIS")
    REDIS_HOST: str = Field("localhost", validation_alias="REDIS_HOST")
    REDIS_PORT: int = Field(6379, validation_alias="REDIS_PORT")
    REDIS_DB: int = Field(0, validation_alias="REDIS_DB")
    REDIS_TIMEOUT: int = Field(5, validation_alias="REDIS_TIMEOUT")  # Connection timeout in seconds
    
    # JWT Auth
    SECRET_KEY: str = Field(default="", validation_alias="SECRET_KEY")
    ALGORITHM: str = Field("HS256", validation_alias="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    PLUGIN_TOKEN_EXPIRE_DAYS: int = Field(30, validation_alias="PLUGIN_TOKEN_EXPIRE_DAYS")
    
    # App mode
    APP_MODE: str = Field("api", validation_alias="APP_MODE")  # "api" or "ui"
    
    # AI Provider
    AI_PROVIDER: str = Field("claude", validation_alias="AI_PROVIDER")
    
    # File settings
    MAX_FILE_SIZE_MB: int = Field(25, validation_alias="MAX_FILE_SIZE_MB")
    ALLOWED_FILE_TYPES: str = Field("pdf,docx,pptx,xlsx,txt,csv", validation_alias="ALLOWED_FILE_TYPES")
    UPLOAD_DIR: str = Field("uploads", validation_alias="UPLOAD_DIR")
    
    # Server Settings (using SERVER_HOST and SERVER_PORT from .env)
    HOST: str = Field("0.0.0.0", validation_alias="HOST")  # Fallback if HOST is used
    PORT: int = Field(8000, validation_alias="PORT")  # Fallback if PORT is used
    DEBUG: bool = Field(False, validation_alias="DEBUG")
    RELOAD: bool = Field(False, validation_alias="RELOAD")  # Auto-reload in production
    
    # CORS Settings
    CORS_ORIGINS: str = Field("http://localhost:3000,http://127.0.0.1:3000,http://10.199.100.54:3000", validation_alias="CORS_ORIGINS")  # Comma-separated list
    CORS_METHODS: str = Field("*", validation_alias="CORS_METHODS")
    CORS_HEADERS: str = Field("*", validation_alias="CORS_HEADERS")
    
    # Activity Tracking
    ACTIVITY_LOG_DIR: str = Field("activity_logs", validation_alias="ACTIVITY_LOG_DIR")
    ACTIVITY_RETENTION_DAYS: int = Field(30, validation_alias="ACTIVITY_RETENTION_DAYS")

    # API credentials
    API_USERNAME: str = Field("your_username", validation_alias="API_USERNAME")
    API_PASSWORD_HASH: str = Field("your_hashed_password", validation_alias="API_PASSWORD_HASH")

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