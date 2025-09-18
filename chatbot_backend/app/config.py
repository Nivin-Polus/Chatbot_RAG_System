# app/config.py

import os
from dotenv import load_dotenv
from pydantic import BaseSettings, Field

# Load .env file
load_dotenv()


class Settings(BaseSettings):
    # Claude API
    CLAUDE_API_KEY: str = Field(..., env="CLAUDE_API_KEY")
    CLAUDE_API_URL: str = Field("https://api.anthropic.com/v1/complete", env="CLAUDE_API_URL")
    CLAUDE_MODEL: str = Field("claude-v1", env="CLAUDE_MODEL")
    CLAUDE_MAX_TOKENS: int = Field(1000, env="CLAUDE_MAX_TOKENS")
    CLAUDE_TEMPERATURE: float = Field(0.0, env="CLAUDE_TEMPERATURE")
    
    # Vector DB (Qdrant)
    VECTOR_DB_URL: str = Field("http://localhost:6333", env="VECTOR_DB_URL")
    
    # Redis (optional)
    USE_REDIS: bool = Field(False, env="USE_REDIS")
    REDIS_HOST: str = Field("localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(6379, env="REDIS_PORT")
    REDIS_DB: int = Field(0, env="REDIS_DB")
    
    # JWT Auth
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = Field("HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # App mode
    APP_MODE: str = Field("api", env="APP_MODE")  # "api" or "ui"
    
    # File settings
    MAX_FILE_SIZE_MB: int = Field(25, env="MAX_FILE_SIZE_MB")
    ALLOWED_FILE_TYPES: str = Field("pdf,docx,pptx,xlsx,txt", env="ALLOWED_FILE_TYPES")

    # API credentials
    API_USERNAME: str = Field("your_username", env="API_USERNAME")
    API_PASSWORD_HASH: str = Field("your_hashed_password", env="API_PASSWORD_HASH")

    class Config:
        env_file = ".env"


# Instantiate settings
settings = Settings()
