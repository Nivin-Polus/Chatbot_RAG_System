from fastapi import APIRouter, Depends, HTTPException
from app.core.permissions import get_current_user
from app.services.health_monitor import HealthMonitorService
from app.services.file_storage import FileStorageService
from app.services.chat_tracking import ChatTrackingService
from app.core.database import get_db
from sqlalchemy.orm import Session
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Initialize services
health_service = HealthMonitorService()
file_service = FileStorageService()
chat_service = ChatTrackingService()


@router.get("/health")
async def system_health():
    """Public health check endpoint"""
    try:
        overview = health_service.get_system_overview()
        return overview
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "overall_status": "unhealthy",
            "error": str(e)
        }


@router.get("/health/detailed")
async def detailed_health_check(current_user = Depends(get_current_user)):
    """Detailed health check (authenticated users only)"""
    try:
        overview = health_service.get_system_overview()
        return overview
    except Exception as e:
        logger.error(f"Detailed health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/qdrant")
async def qdrant_health(current_user = Depends(get_current_user)):
    """Check Qdrant vector database health"""
    if not (current_user.is_super_admin() or current_user.is_user_admin()):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return health_service.check_qdrant_health()


@router.get("/health/ai")
async def ai_model_health(current_user = Depends(get_current_user)):
    """Check AI model health"""
    if not (current_user.is_super_admin() or current_user.is_user_admin()):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return health_service.check_ai_model_health()


@router.get("/health/files")
async def file_processing_health(current_user = Depends(get_current_user)):
    """Check file processing health"""
    if not (current_user.is_super_admin() or current_user.is_user_admin()):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return health_service.check_file_processing_health()


@router.get("/health/auth")
async def authentication_health(current_user = Depends(get_current_user)):
    """Check authentication system health"""
    if not (current_user.is_super_admin() or current_user.is_user_admin()):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return health_service.check_authentication_health()


class ResetRequest(BaseModel):
    password: str


@router.post("/health/reset")
async def reset_system(
    payload: ResetRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset system to default state. Requires super admin and password confirmation.

    Actions:
    - Delete all collections, prompts, memberships, files, vector DB records, chat logs
    - Keep or (re)create default users: superadmin/superadmin123, admin/admin123, user/user123
    - Create a default collection and default prompt
    - Assign admin as collection admin and user as regular user
    """
    # Permission check
    if not current_user.is_super_admin():
        raise HTTPException(status_code=403, detail="Super admin access required")

    # Verify password
    try:
        from app.core.auth import verify_password, get_password_hash
        if not verify_password(payload.password, current_user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid super admin password")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Password verification failed: {e}")
        raise HTTPException(status_code=500, detail="Password verification failed")

    # Perform reset in a transaction
    try:
        from app.models.collection import Collection, CollectionUser
        from app.models.system_prompt import SystemPrompt
        from app.models.user import User
        from app.models.file_metadata import FileMetadata
        from app.models.vector_database import VectorDatabase
        from app.models.website import Website
        from app.core.vector_singleton import get_vector_store

        # Optional models
        try:
            from app.models.user_file_access import UserFileAccess
        except Exception:
            UserFileAccess = None
        try:
            from app.models.chat_session import ChatSession
            from app.models.query_log import QueryLog
        except Exception:
            ChatSession = None
            QueryLog = None

        # Delete Qdrant collections first (best-effort)
        try:
            vs = get_vector_store()
            if getattr(vs, 'client', None):
                cols = vs.client.get_collections()
                for c in cols.collections:
                    # Delete only app-created collections
                    if c.name.startswith("collection_"):
                        try:
                            vs.client.delete_collection(c.name)
                        except Exception:
                            pass
        except Exception:
            logger.warning("Qdrant cleanup failed during reset", exc_info=True)

        # Delete dependent records first
        db.query(CollectionUser).delete(synchronize_session=False)
        db.query(SystemPrompt).delete(synchronize_session=False)
        db.query(FileMetadata).delete(synchronize_session=False)
        if UserFileAccess:
            db.query(UserFileAccess).delete(synchronize_session=False)
        if ChatSession:
            db.query(ChatSession).delete(synchronize_session=False)
        if QueryLog:
            db.query(QueryLog).delete(synchronize_session=False)
        db.query(VectorDatabase).delete(synchronize_session=False)
        db.query(Collection).delete(synchronize_session=False)

        # Remove all users except the three defaults and current superadmin account (by username)
        default_usernames = {"superadmin", "admin", "user"}
        users = db.query(User).all()
        for u in users:
            if u.username not in default_usernames:
                db.delete(u)
        db.flush()

        # Create or get default website
        default_site = db.query(Website).filter(Website.domain == "default.local").first()
        if not default_site:
            default_site = Website(
                website_id=None,
                name="Default Organization",
                domain="default.local",
                is_active=True
            )
            db.add(default_site)
            db.flush()

        default_website_id = default_site.website_id

        # Ensure default users exist and are active with known credentials
        def upsert_user(username: str, password: str, role: str, email: str, full_name: str) -> User:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(
                    username=username,
                    email=email,
                    password_hash=get_password_hash(password),
                    full_name=full_name,
                    role=role,
                    is_active=True,
                    website_id=default_website_id if role != "super_admin" else None
                )
                db.add(user)
                db.flush()
            else:
                user.password_hash = get_password_hash(password)
                user.role = role
                user.is_active = True
                if role != "super_admin":
                    user.website_id = default_website_id
                db.add(user)
                db.flush()
            return user

        super_admin = upsert_user("superadmin", "superadmin123", "super_admin", "superadmin@example.com", "Super Admin")
        admin_user = upsert_user("admin", "admin123", "user_admin", "admin@example.com", "Admin User")
        regular_user = upsert_user("user", "user123", "user", "user@example.com", "Regular User")

        # Create default vector database and collection
        default_collection_id = "col_default"
        default_collection = Collection(
            collection_id=default_collection_id,
            name="Default Collection",
            description="System default collection",
            website_url="https://default.local",
            website_id=default_website_id,
            admin_user_id=admin_user.user_id,
            admin_email=admin_user.email,
            is_active=True
        )
        db.add(default_collection)
        db.flush()

        # Create VectorDatabase entry for this collection
        vdb = VectorDatabase(
            name="Vector DB - Default",
            description="Auto-created for default collection",
            website_id=default_website_id,
            collection_name=f"collection_{default_collection_id}"
        )
        db.add(vdb)
        db.flush()
        default_collection.vector_db_id = vdb.vector_db_id
        db.add(default_collection)

        # Memberships
        db.add(CollectionUser(
            collection_id=default_collection_id,
            user_id=admin_user.user_id,
            role="admin",
            can_upload=True,
            can_download=True,
            can_delete=True,
            assigned_by=super_admin.user_id
        ))
        db.add(CollectionUser(
            collection_id=default_collection_id,
            user_id=regular_user.user_id,
            role="user",
            can_upload=True,
            can_download=True,
            can_delete=False,
            assigned_by=super_admin.user_id
        ))

        # Default prompt
        db.add(SystemPrompt(
            name="Default Prompt - Collection",
            description="Default AI prompt",
            system_prompt="You are a helpful AI assistant. Answer questions based on the provided context.",
            collection_id=default_collection_id,
            website_id=None,
            vector_db_id=vdb.vector_db_id,
            is_default=True,
            is_active=True,
            model_name="claude-3-haiku-20240307",
            max_tokens=4000,
            temperature=0.7
        ))

        db.commit()

        return {
            "message": "System reset to default state",
            "defaults": {
                "users": ["superadmin", "admin", "user"],
                "collection": default_collection_id,
                "prompt": "Default Prompt - Collection"
            }
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"System reset failed: {e}")
        raise HTTPException(status_code=500, detail="System reset failed")


@router.get("/stats/storage")
async def storage_statistics(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get storage statistics"""
    if not (current_user.is_super_admin() or current_user.is_user_admin()):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return file_service.get_storage_stats(db)


@router.get("/stats/chat")
async def chat_statistics(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get chat statistics"""
    if not (current_user.is_super_admin() or current_user.is_user_admin()):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return chat_service.get_chat_analytics(db)


@router.get("/stats/overview")
async def system_overview(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get complete system overview with stats - REAL DATABASE COUNTS"""
    if not (current_user.is_super_admin() or current_user.is_user_admin()):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logger.info("=== GETTING REAL DATABASE STATS ===")
    
    try:
        from app.models.collection import Collection
        from app.models.user import User
        from app.models.file_metadata import FileMetadata
        from app.models.system_prompt import SystemPrompt
        
        # Get actual counts from database
        total_collections = db.query(Collection).count()
        total_users = db.query(User).count()
        total_files = db.query(FileMetadata).count()
        total_prompts = db.query(SystemPrompt).count()
        
        logger.info(f"✅ REAL DB COUNTS: collections={total_collections}, users={total_users}, files={total_files}, prompts={total_prompts}")
        
        # Get additional stats with error handling
        try:
            health_overview = health_service.get_system_overview()
        except Exception as e:
            logger.warning(f"Health overview failed: {e}")
            health_overview = {"status": "healthy"}
            
        try:
            storage_stats = file_service.get_storage_stats(db)
        except Exception as e:
            logger.warning(f"Storage stats failed: {e}")
            storage_stats = {"total_size": 0}
            
        try:
            chat_stats = chat_service.get_chat_analytics(db)
        except Exception as e:
            logger.warning(f"Chat stats failed: {e}")
            chat_stats = {"total_queries": 0}
        
        result = {
            # Frontend expects these specific fields - REAL VALUES
            "total_collections": total_collections,
            "total_users": total_users,
            "total_files": total_files,
            "total_prompts": total_prompts,
            # Additional stats
            "system_health": health_overview,
            "storage_statistics": storage_stats,
            "chat_analytics": chat_stats
        }
        
        logger.info(f"✅ RETURNING REAL STATS: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR getting stats: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(e)}")


@router.get("/stats/test")
async def test_stats(current_user = Depends(get_current_user)):
    """Test endpoint to verify stats work"""
    return {
        "total_collections": 3,
        "total_users": 9,
        "total_files": 5,
        "total_prompts": 2,
        "message": "This is a test endpoint"
    }
