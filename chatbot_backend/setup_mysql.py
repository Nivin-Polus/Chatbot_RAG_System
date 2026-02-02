#!/usr/bin/env python3
"""
MySQL Database Setup Script for RAG Chatbot System

This script helps set up the MySQL database for the RAG chatbot system.
It creates the database, tables, and default users.

Usage:
    python setup_mysql.py

Requirements:
    - MySQL server running
    - PyMySQL installed
    - Proper database credentials in .env file
"""

import sys
import logging
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.config import settings
from app.core.database import create_database_if_not_exists, init_database
from app.core.auth import create_user

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_mysql_connection():
    """Check if MySQL server is accessible"""
    try:
        import pymysql
        
        # Test connection without database
        connection = pymysql.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            charset=settings.DATABASE_CHARSET
        )
        connection.close()
        logger.info("✅ MySQL server connection successful")
        return True
        
    except Exception as e:
        logger.error(f"❌ MySQL server connection failed: {e}")
        return False

def setup_database():
    """Set up the complete database"""
    try:
        logger.info("🚀 Starting MySQL database setup...")
        
        # Check MySQL connection
        if not check_mysql_connection():
            logger.error("❌ Cannot connect to MySQL server. Please check your configuration.")
            return False
        
        # Create database if it doesn't exist
        logger.info("📋 Creating database if needed...")
        create_database_if_not_exists()
        
        # Initialize database (create tables)
        logger.info("🏗️ Initializing database tables...")
        init_database()
        
        # Create default users
        logger.info("👥 Creating default users...")
        
        # Create admin user
        admin_user = create_user(
            username="admin",
            password="admin123",
            email="admin@chatbot.local",
            full_name="System Administrator",
            role="admin"
        )
        
        if admin_user:
            logger.info("✅ Admin user created: admin/admin123")
        else:
            logger.warning("⚠️ Admin user already exists or creation failed")
        
        # Create regular user
        regular_user = create_user(
            username="user",
            password="user123",
            email="user@chatbot.local",
            full_name="Regular User",
            role="user"
        )
        
        if regular_user:
            logger.info("✅ Regular user created: user/user123")
        else:
            logger.warning("⚠️ Regular user already exists or creation failed")
        
        logger.info("🎉 Database setup completed successfully!")
        
        # Print configuration summary
        print("\n" + "="*60)
        print("DATABASE SETUP SUMMARY")
        print("="*60)
        print(f"Database Type: {settings.DATABASE_TYPE}")
        print(f"Host: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}")
        print(f"Database: {settings.DATABASE_NAME}")
        print(f"User: {settings.DATABASE_USER}")
        print(f"Charset: {settings.DATABASE_CHARSET}")
        print("\nDefault Accounts:")
        print("- Admin: admin/admin123")
        print("- User: user/user123")
        print("\nNext Steps:")
        print("1. Update your .env file with proper database credentials")
        print("2. Start the application: python -m uvicorn app.main:app --reload")
        print("3. Access the application at http://localhost:8000")
        print("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        return False

def verify_setup():
    """Verify the database setup"""
    try:
        from app.core.database import get_db_health, get_database_stats
        
        logger.info("🔍 Verifying database setup...")
        
        # Check database health
        health = get_db_health()
        if health.get("status") == "healthy":
            logger.info("✅ Database health check passed")
            logger.info(f"   Version: {health.get('version', 'Unknown')}")
            logger.info(f"   Current DB: {health.get('current_database', 'Unknown')}")
        else:
            logger.error(f"❌ Database health check failed: {health.get('error')}")
            return False
        
        # Get database statistics
        stats = get_database_stats()
        if "error" not in stats:
            logger.info("📊 Database statistics:")
            logger.info(f"   Total tables: {len(stats.get('tables', []))}")
            logger.info(f"   Total rows: {stats.get('total_rows', 0)}")
            logger.info(f"   Total size: {stats.get('total_size_mb', 0)} MB")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🔧 MySQL Database Setup for RAG Chatbot System")
    print("=" * 50)
    
    # Check configuration
    logger.info("⚙️ Checking configuration...")
    
    if not settings.DATABASE_PASSWORD:
        logger.warning("⚠️ DATABASE_PASSWORD is empty. This might cause connection issues.")
    
    if settings.DATABASE_TYPE.lower() != "mysql":
        logger.warning(f"⚠️ DATABASE_TYPE is set to '{settings.DATABASE_TYPE}', expected 'mysql'")
    
    # Setup database
    if not setup_database():
        logger.error("❌ Database setup failed!")
        sys.exit(1)
    
    # Verify setup
    if not verify_setup():
        logger.error("❌ Database verification failed!")
        sys.exit(1)
    
    logger.info("🎉 All setup and verification completed successfully!")

if __name__ == "__main__":
    main()
