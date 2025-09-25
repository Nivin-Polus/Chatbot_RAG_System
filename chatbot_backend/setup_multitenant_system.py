#!/usr/bin/env python3
"""
Complete Multi-Tenant System Setup
This script sets up the exact workflow you described:
1. Super Admin can create User Admins
2. User Admins can upload/delete data and manage users in their website
3. Regular Users get restricted access to specific data
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def setup_database_tables():
    """Create all multi-tenant tables"""
    try:
        from app.config import settings
        from sqlalchemy import create_engine, text
        
        # Import ALL models to ensure they're registered
        from app.models.base import Base
        from app.models.website import Website
        from app.models.user import User
        from app.models.file_metadata import FileMetadata
        from app.models.user_file_access import UserFileAccess
        from app.models.query_log import QueryLog
        
        print("🔄 Setting up multi-tenant database tables...")
        
        # Create engine
        database_url = settings.database_url
        engine = create_engine(database_url)
        
        print(f"📍 Database URL: {database_url}")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT DATABASE()"))
            current_db = result.fetchone()
            print(f"🔗 Connected to database: {current_db[0]}")
        
        # Create all tables
        print("📋 Creating multi-tenant tables...")
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES"))
            tables = result.fetchall()
            
            print(f"✅ Created/verified {len(tables)} tables:")
            for table in tables:
                print(f"  - {table[0]}")
        
        engine.dispose()
        return len(tables) > 0
        
    except Exception as e:
        print(f"❌ Failed to setup tables: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_multitenant_users():
    """Create the multi-tenant user hierarchy"""
    try:
        from app.config import settings
        from app.models.website import Website
        from app.models.user import User
        from passlib.context import CryptContext
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        print("\n👥 Setting up multi-tenant user system...")
        
        # Create engine and session
        database_url = settings.database_url
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        db = SessionLocal()
        
        try:
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            # 1. Create Default Website (if not exists)
            default_website = db.query(Website).filter(Website.name == "Default Organization").first()
            if not default_website:
                default_website = Website(
                    name="Default Organization",
                    domain="localhost",
                    description="Default organization for initial setup",
                    admin_email="admin@chatbot.local",
                    is_active=True,
                    max_users=100,
                    max_files=1000,
                    max_storage_mb=10240
                )
                db.add(default_website)
                db.flush()
                print("✅ Created Default Organization website")
            else:
                print("ℹ️ Default Organization website already exists")
            
            # 2. Create Super Admin (global access, no website)
            super_admin = db.query(User).filter(User.username == "superadmin").first()
            if not super_admin:
                super_admin = User(
                    username="superadmin",
                    email="superadmin@chatbot.local",
                    password_hash=pwd_context.hash("superadmin123"),
                    full_name="Super Administrator",
                    role="super_admin",
                    website_id=None,  # Super admin not tied to any website
                    is_active=True
                )
                db.add(super_admin)
                print("✅ Created Super Admin: superadmin/superadmin123")
            else:
                print("ℹ️ Super Admin already exists")
            
            # 3. Create User Admin for Default Organization
            user_admin = db.query(User).filter(User.username == "admin").first()
            if not user_admin:
                user_admin = User(
                    username="admin",
                    email="admin@chatbot.local",
                    password_hash=pwd_context.hash("admin123"),
                    full_name="Website Administrator",
                    role="user_admin",
                    website_id=default_website.website_id,
                    is_active=True
                )
                db.add(user_admin)
                print("✅ Created User Admin: admin/admin123")
            else:
                # Update existing admin to have correct website_id
                user_admin.website_id = default_website.website_id
                user_admin.role = "user_admin"
                print("ℹ️ Updated existing admin user")
            
            # 4. Create Regular User for Default Organization
            regular_user = db.query(User).filter(User.username == "user").first()
            if not regular_user:
                regular_user = User(
                    username="user",
                    email="user@chatbot.local",
                    password_hash=pwd_context.hash("user123"),
                    full_name="Regular User",
                    role="user",
                    website_id=default_website.website_id,
                    is_active=True
                )
                db.add(regular_user)
                print("✅ Created Regular User: user/user123")
            else:
                # Update existing user to have correct website_id
                regular_user.website_id = default_website.website_id
                regular_user.role = "user"
                print("ℹ️ Updated existing regular user")
            
            db.commit()
            
            print("\n🎯 Multi-Tenant System Ready!")
            print("📋 User Hierarchy:")
            print("  1. Super Admin (superadmin/superadmin123)")
            print("     - Can create websites and user admins")
            print("     - Global access to all data")
            print("  2. User Admin (admin/admin123)")
            print("     - Can upload/delete files in their website")
            print("     - Can create and manage regular users")
            print("     - Can assign file access to users")
            print("  3. Regular User (user/user123)")
            print("     - Can only access files explicitly granted to them")
            print("     - Can chat with accessible documents")
            
            return True
            
        finally:
            db.close()
            engine.dispose()
            
    except Exception as e:
        print(f"❌ Failed to create users: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_system():
    """Verify the multi-tenant system is working"""
    try:
        from app.config import settings
        from app.models.website import Website
        from app.models.user import User
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        print("\n🔍 Verifying multi-tenant system...")
        
        # Create engine and session
        database_url = settings.database_url
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        db = SessionLocal()
        
        try:
            # Check websites
            websites = db.query(Website).all()
            print(f"📋 Websites: {len(websites)}")
            for website in websites:
                print(f"  - {website.name} (ID: {website.website_id})")
            
            # Check users by role
            super_admins = db.query(User).filter(User.role == "super_admin").all()
            user_admins = db.query(User).filter(User.role == "user_admin").all()
            regular_users = db.query(User).filter(User.role == "user").all()
            
            print(f"👑 Super Admins: {len(super_admins)}")
            for user in super_admins:
                print(f"  - {user.username} (website: {user.website_id or 'None - Global'})")
            
            print(f"👨‍💼 User Admins: {len(user_admins)}")
            for user in user_admins:
                website_name = "Unknown"
                if user.website_id:
                    website = db.query(Website).filter(Website.website_id == user.website_id).first()
                    website_name = website.name if website else "Unknown"
                print(f"  - {user.username} (website: {website_name})")
            
            print(f"👤 Regular Users: {len(regular_users)}")
            for user in regular_users:
                website_name = "Unknown"
                if user.website_id:
                    website = db.query(Website).filter(Website.website_id == user.website_id).first()
                    website_name = website.name if website else "Unknown"
                print(f"  - {user.username} (website: {website_name})")
            
            return True
            
        finally:
            db.close()
            engine.dispose()
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Multi-Tenant RAG Chatbot System Setup")
    print("=" * 50)
    
    # Step 1: Setup database tables
    if not setup_database_tables():
        print("❌ Failed to setup database tables")
        sys.exit(1)
    
    # Step 2: Create multi-tenant users
    if not create_multitenant_users():
        print("❌ Failed to create multi-tenant users")
        sys.exit(1)
    
    # Step 3: Verify system
    if not verify_system():
        print("❌ System verification failed")
        sys.exit(1)
    
    print("\n🎉 Multi-Tenant System Setup Complete!")
    print("\n📖 Next Steps:")
    print("1. Restart your server: python start_server.py")
    print("2. Login as Super Admin: superadmin/superadmin123")
    print("3. Create new websites and user admins via API")
    print("4. User admins can upload files and manage users")
    print("5. Regular users get restricted access to assigned files")
    
    print("\n🔗 API Endpoints:")
    print("- POST /websites/ - Create new website (super admin)")
    print("- POST /users/ - Create new user (super admin, user admin)")
    print("- POST /files/upload - Upload files (admin roles)")
    print("- POST /files/{file_id}/access - Grant file access")

if __name__ == "__main__":
    main()
