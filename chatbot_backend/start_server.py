#!/usr/bin/env python3
"""
Startup script for the RAG Chatbot Backend
"""

import os
import sys
import logging
from pathlib import Path

# Load .env file first
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if all required environment variables are set"""
    try:
        # Import settings to trigger .env loading
        from app.config import settings
        
        # Check if critical settings are available
        if not settings.CLAUDE_API_KEY:
            logger.warning("CLAUDE_API_KEY is empty - AI responses may not work")
        if not settings.SECRET_KEY:
            logger.warning("SECRET_KEY is empty - authentication may not work")
            
        if settings.CLAUDE_API_KEY and settings.SECRET_KEY:
            logger.info("✅ All environment variables are set")
            return True
        else:
            logger.warning("Some environment variables are missing")
            return False
            
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return False

def check_dependencies():
    """Check if all required packages are installed"""
    try:
        import sqlalchemy
        import fastapi
        import uvicorn
        import anthropic
        import qdrant_client
        logger.info("✅ All required packages are installed")
        return True
    except ImportError as e:
        logger.error(f"❌ Missing dependency: {e}")
        logger.info("Please run: pip install -r requirements.txt")
        return False

def initialize_database():
    """Initialize the database"""
    try:
        from app.core.database import init_database
        init_database()
        logger.info("✅ Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False

def start_server():
    """Start the FastAPI server"""
    try:
        import uvicorn
        from app.main import app
        from app.config import settings
        
        # Use effective host and port (prefer SERVER_HOST/SERVER_PORT from .env)
        host = settings.effective_host
        port = settings.effective_port
        
        logger.info("🚀 Starting RAG Chatbot Backend...")
        logger.info(f"📍 Server will be available at: http://{host}:{port}")
        logger.info(f"📖 API Documentation: http://{host}:{port}/docs")
        logger.info(f"🔍 Health Check: http://{host}:{port}/health")
        logger.info(f"🔧 Debug Mode: {settings.DEBUG}")
        logger.info(f"🔄 Auto-reload: {settings.RELOAD}")
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=settings.RELOAD,
            log_level="info" if not settings.DEBUG else "debug",
            limit_concurrency=1000,
            limit_max_requests=10000,
            timeout_keep_alive=5
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        return False

def main():
    """Main startup function"""
    logger.info("🤖 RAG Chatbot Backend Startup")
    logger.info("=" * 50)
    logger.info("🛠️ Startup fingerprint: keyword-only save_file patch active")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check environment
    if not check_environment():
        logger.info("⚠️  Continuing with missing environment variables...")
    
    # Initialize database
    if not initialize_database():
        logger.error("Failed to initialize database")
        sys.exit(1)
    
    # Start server
    start_server()

if __name__ == "__main__":
    main()
