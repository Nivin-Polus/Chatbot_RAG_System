#!/usr/bin/env python3
"""Migrate file_binaries table to support larger files"""

import sys
import os

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from sqlalchemy import create_engine, text
import logging

# Database configuration
DATABASE_URL = "mysql+pymysql://root:@localhost:3306/chatbot_rag_system"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_file_storage():
    """Migrate file_binaries table to use LONGBLOB for larger files"""
    print("=== Migrating File Storage for Large Files ===")
    
    try:
        # Get database connection
        engine = create_engine(DATABASE_URL)
        
        print(f"Connected to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local'}")
        
        with engine.connect() as conn:
            # Check current column type
            result = conn.execute(text("""
                SELECT COLUMN_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'file_binaries' 
                AND COLUMN_NAME = 'data'
            """))
            
            current_type = result.fetchone()
            if current_type:
                print(f"Current data column type: {current_type[0]}")
                
                if 'longblob' not in current_type[0].lower():
                    print("🔧 Updating data column to LONGBLOB...")
                    
                    # Alter table to use LONGBLOB
                    conn.execute(text("""
                        ALTER TABLE file_binaries 
                        MODIFY COLUMN data LONGBLOB NOT NULL
                    """))
                    
                    conn.commit()
                    print("✅ Successfully updated data column to LONGBLOB")
                    
                    # Verify the change
                    result = conn.execute(text("""
                        SELECT COLUMN_TYPE 
                        FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() 
                        AND TABLE_NAME = 'file_binaries' 
                        AND COLUMN_NAME = 'data'
                    """))
                    
                    new_type = result.fetchone()
                    if new_type:
                        print(f"✅ Verified new column type: {new_type[0]}")
                else:
                    print("✅ Column is already LONGBLOB - no migration needed")
            else:
                print("❌ file_binaries table or data column not found")
                
                # Check if table exists
                result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'file_binaries'
                """))
                
                table_exists = result.fetchone()[0]
                if table_exists == 0:
                    print("ℹ️  file_binaries table doesn't exist - will be created with LONGBLOB")
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"❌ Migration failed: {e}")
        return False
    
    print("\n=== Migration Complete ===")
    print("📋 Next Steps:")
    print("1. Restart your backend server")
    print("2. Try uploading files again")
    print("3. Files up to 4GB should now be supported")
    
    return True

if __name__ == "__main__":
    migrate_file_storage()
