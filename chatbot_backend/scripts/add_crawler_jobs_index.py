#!/usr/bin/env python3
"""
Add index on crawler_jobs.created_at column
This fixes the "Out of sort memory" error when querying jobs ordered by created_at.

Usage:
    python scripts/add_crawler_jobs_index.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text, inspect
from app.config import settings


def add_index():
    """Add index on crawler_jobs.created_at if it doesn't exist."""
    try:
        # Create engine
        engine = create_engine(settings.database_url)
        
        print("🔗 Connecting to database...")
        with engine.connect() as conn:
            # Check if index already exists
            inspector = inspect(engine)
            indexes = inspector.get_indexes('crawler_jobs')
            
            index_exists = any(
                idx['name'] == 'ix_crawler_jobs_created_at' 
                for idx in indexes
            )
            
            if index_exists:
                print("✅ Index 'ix_crawler_jobs_created_at' already exists")
                return True
            
            # Check if table exists
            if 'crawler_jobs' not in inspector.get_table_names():
                print("⚠️  Table 'crawler_jobs' does not exist yet")
                print("   The index will be created automatically when the table is created")
                return True
            
            print("📋 Creating index on crawler_jobs.created_at...")
            
            # Create index
            conn.execute(text("""
                CREATE INDEX ix_crawler_jobs_created_at 
                ON crawler_jobs(created_at DESC)
            """))
            conn.commit()
            
            print("✅ Index 'ix_crawler_jobs_created_at' created successfully")
            
            # Verify
            indexes = inspector.get_indexes('crawler_jobs')
            index_exists = any(
                idx['name'] == 'ix_crawler_jobs_created_at' 
                for idx in indexes
            )
            
            if index_exists:
                print("✅ Index verified and ready to use")
                return True
            else:
                print("⚠️  Index creation reported success but verification failed")
                return False
                
    except Exception as e:
        print(f"❌ Error adding index: {e}")
        return False
    finally:
        if 'engine' in locals():
            engine.dispose()


if __name__ == "__main__":
    print("=" * 60)
    print("Add Index on crawler_jobs.created_at")
    print("=" * 60)
    print()
    
    success = add_index()
    
    print()
    if success:
        print("✅ Migration completed successfully")
        print()
        print("The index will improve query performance when listing crawl jobs")
        print("ordered by creation date. This fixes the 'Out of sort memory' error.")
    else:
        print("❌ Migration failed. Please check the error messages above.")
        sys.exit(1)

