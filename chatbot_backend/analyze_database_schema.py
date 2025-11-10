#!/usr/bin/env python3
"""
Simple Database Schema Fix
Connects to database and removes problematic columns
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_database_schema():
    """Fix database schema by removing vector_db_id columns"""

    try:
        # Create database connection
        database_url = settings.database_url
        logger.info(f"Connecting to database: {settings.DATABASE_TYPE}")
        logger.info(f"Database: {settings.DATABASE_NAME}")

        engine = create_engine(database_url)

        with engine.connect() as connection:
            logger.info("✅ Connected to database successfully")

            # Check current database
            result = connection.execute(text("SELECT DATABASE()"))
            current_db = result.fetchone()[0]
            logger.info(f"Current database: {current_db}")

            # List all tables
            result = connection.execute(text("SHOW TABLES"))
            tables = result.fetchall()
            logger.info(f"Available tables: {[table[0] for table in tables]}")

            # Check if file_metadata table has vector_db_id column
            try:
                result = connection.execute(text("""
                    SELECT COLUMN_NAME, COLUMN_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'file_metadata'
                    AND TABLE_SCHEMA = DATABASE()
                """))

                columns = result.fetchall()
                logger.info("file_metadata table columns:")
                for col in columns:
                    logger.info(f"  {col[0]}: {col[1]}")

                # Check if vector_db_id exists
                has_vector_db_id = any(col[0] == 'vector_db_id' for col in columns)
                if has_vector_db_id:
                    logger.info("⚠️  Found vector_db_id column in file_metadata. This needs to be removed.")
                    logger.info("Run this SQL command manually:")
                    logger.info("ALTER TABLE file_metadata DROP COLUMN vector_db_id;")
                else:
                    logger.info("✅ file_metadata table doesn't have vector_db_id column")

            except Exception as e:
                logger.warning(f"Could not check file_metadata columns: {e}")

            # Check system_prompts table
            try:
                result = connection.execute(text("""
                    SELECT COLUMN_NAME, COLUMN_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'system_prompts'
                    AND TABLE_SCHEMA = DATABASE()
                """))

                columns = result.fetchall()
                logger.info("system_prompts table columns:")
                for col in columns:
                    logger.info(f"  {col[0]}: {col[1]}")

                # Check if collection_id exists
                has_collection_id = any(col[0] == 'collection_id' for col in columns)
                if has_collection_id:
                    logger.info("⚠️  Found collection_id column in system_prompts. This needs to be removed.")
                    logger.info("Run this SQL command manually:")
                    logger.info("ALTER TABLE system_prompts DROP COLUMN collection_id;")
                else:
                    logger.info("✅ system_prompts table doesn't have collection_id column")

            except Exception as e:
                logger.warning(f"Could not check system_prompts columns: {e}")

        logger.info("✅ Database analysis completed!")
        logger.info("If you see any columns that need to be removed, run the SQL commands above.")

    except Exception as e:
        logger.error(f"❌ Failed to analyze database: {e}")
        logger.error("Please check your database connection and try again.")
        raise

if __name__ == "__main__":
    print("🔍 Database Schema Analysis Tool")
    print("=" * 50)
    print("This script will analyze your database schema and identify issues.")
    print()

    try:
        fix_database_schema()
        print("\n✅ Database analysis completed!")
        print("Check the output above for any issues that need to be fixed.")
    except Exception as e:
        print(f"\n❌ Failed to analyze database: {e}")
        print("\nAlternative solution:")
        print("1. Connect to your MySQL database manually")
        print("2. Run: DESCRIBE file_metadata;")
        print("3. Run: DESCRIBE system_prompts;")
        print("4. Remove any columns that shouldn't be there:")
        print("   ALTER TABLE file_metadata DROP COLUMN vector_db_id;")
        print("   ALTER TABLE system_prompts DROP COLUMN collection_id;")
        sys.exit(1)
