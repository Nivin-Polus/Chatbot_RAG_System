# app/main.py

from fastapi import FastAPI, APIRouter, Request, Form, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from contextlib import contextmanager
import logging

from app.api import (
    routes_health,
    routes_auth,
    routes_chat,
    routes_collections,
    routes_files,
    routes_activity,
    routes_prompts,
    routes_multitenant_users,
    routes_websites,
    routes_vector_databases,
    routes_plugins,
)
from app.core.database import init_database, create_database_if_not_exists, get_db
from app.config import settings
from app.core.auth import get_token_from_credentials, get_password_hash
from app.services.health_monitor import HealthMonitorService
print("DEBUG: SETTINGS.CORS_ORIGINS =", settings.CORS_ORIGINS)


class TokenRequest(BaseModel):
    username: str
    password: str


# Initialize FastAPI
app = FastAPI(
    title="Knowledge Base Chatbot API",
    description="Backend API for RAG + Claude chatbot with Qdrant vector DB",
    version="0.1.0",
)

# Configure request body size limit (50MB to accommodate file uploads)
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Set max request body size to 50MB (larger than MAX_FILE_SIZE_MB)
        return await call_next(request)

app.add_middleware(RequestSizeLimitMiddleware)

# CORS (configurable for production)
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
methods = [method.strip() for method in settings.CORS_METHODS.split(",")]
headers = [header.strip() for header in settings.CORS_HEADERS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=methods,
    allow_headers=headers,
)

# API router with global prefix
api_router = APIRouter(prefix="/rag")

# Include routers under global prefix
api_router.include_router(routes_auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(routes_files.router, prefix="/files", tags=["Files"])
api_router.include_router(routes_chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(routes_health.router, prefix="/system", tags=["Health & Monitoring"])
api_router.include_router(routes_activity.router, prefix="/activity", tags=["Activity Tracking"])
api_router.include_router(routes_websites.router, prefix="/websites", tags=["Multi-Tenant Websites"])
api_router.include_router(routes_multitenant_users.router, prefix="/users", tags=["Multi-Tenant Users"])
api_router.include_router(routes_vector_databases.router, prefix="/vector-databases", tags=["Vector Database Management"])
api_router.include_router(routes_prompts.router, prefix="/prompts", tags=["System Prompts"])
api_router.include_router(routes_collections.router, tags=["Collections"])
api_router.include_router(routes_plugins.router, tags=["Plugins"])

app.include_router(api_router)


@contextmanager
def get_db_session():
    """Provide a managed DB session"""
    db_gen = get_db()
    db = next(db_gen)
    try:
        yield db
    finally:
        db.close()


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database and other startup tasks"""
    try:
        # Create database if it doesn't exist (MySQL only)
        create_database_if_not_exists()

        # Initialize database connection and create tables
        init_database()

        # Initialize default users if needed
        await _initialize_default_users()

        logging.info("✅ Application startup completed successfully")
    except Exception as e:
        logging.error(f"❌ Failed to initialize application: {str(e)}")
        raise


async def _initialize_default_users():
    """Initialize default users (simplified - no collections)"""
    try:
        from app.core.database import get_db
        from app.models.website import Website
        from app.models.user import User
        from app.models.collection import Collection, CollectionUser
        from app.models.system_prompt import SystemPrompt

        # Get database session
        db_gen = get_db()
        db = next(db_gen)

        try:
            # Check if users already exist
            existing_super_admin = db.query(User).filter(User.role == "super_admin").first()
            existing_user_admin = db.query(User).filter(User.username == "admin").first()
            existing_regular_user = db.query(User).filter(User.username == "user").first()
            existing_plugin_user = db.query(User).filter(User.username == "pluginuser").first()

            # Check if default website already exists
            existing_website = db.query(Website).filter(Website.domain == "localhost").first()

            if not existing_website:
                # Create default website
                default_website = Website(
                    name="Default Organization",
                    domain="localhost",
                    description="Default organization for initial setup",
                    admin_email="admin@chatbot.local",
                    is_active=True,
                )
                db.add(default_website)
                db.flush()  # Get the website_id
                logging.info("✅ Created default website")
            else:
                default_website = existing_website
                logging.info("✅ Using existing default website")

            if not existing_super_admin:
                # Create super admin
                super_admin = User(
                    username="superadmin",
                    email="superadmin@chatbot.local",
                    password_hash=get_password_hash("superadmin123"),
                    full_name="Super Administrator",
                    role="super_admin",
                    website_id=None,
                    is_active=True,
                )
                db.add(super_admin)
                db.flush()
                logging.info("✅ Created super admin")
            else:
                super_admin = existing_super_admin
                logging.info("✅ Using existing super admin")

            if not existing_user_admin:
                # Create user admin for default website
                user_admin = User(
                    username="admin",
                    email="admin@chatbot.local",
                    password_hash=get_password_hash("admin123"),
                    full_name="Administrator",
                    role="user_admin",
                    website_id=default_website.website_id,
                    is_active=True,
                )
                db.add(user_admin)
                db.flush()
                logging.info("✅ Created admin user")
            else:
                user_admin = existing_user_admin
                logging.info("✅ Using existing admin user")

            if not existing_regular_user:
                regular_user = User(
                    username="user",
                    email="user@chatbot.local",
                    password_hash=get_password_hash("user123"),
                    full_name="Regular User",
                    role="user",
                    website_id=default_website.website_id,
                    is_active=True,
                )
                db.add(regular_user)
                db.flush()
                logging.info("✅ Created regular user")
            else:
                regular_user = existing_regular_user
                logging.info("✅ Using existing regular user")

            if not existing_plugin_user:
                plugin_user = User(
                    username="pluginuser",
                    email="pluginuser@chatbot.local",
                    password_hash=get_password_hash("plugin123"),
                    full_name="Plugin User",
                    role="plugin_user",
                    website_id=default_website.website_id,
                    is_active=True,
                )
                db.add(plugin_user)
                db.flush()
                logging.info("✅ Created plugin user")
            else:
                plugin_user = existing_plugin_user
                if plugin_user.website_id != default_website.website_id:
                    plugin_user.website_id = default_website.website_id
                logging.info("✅ Using existing plugin user")

            default_collection = db.query(Collection).filter(Collection.collection_id == "col_default").first()
            if not default_collection:
                default_collection = Collection(
                    collection_id="col_default",
                    name="Default Collection",
                    description="Default collection created during setup",
                    website_id=default_website.website_id,
                    website_url="https://localhost/",
                    admin_user_id=user_admin.user_id,
                    admin_email=user_admin.email,
                    is_active=True,
                )
                db.add(default_collection)
                db.flush()
                logging.info("✅ Created default collection for plugin user assignment")

            plugin_membership = db.query(CollectionUser).filter(
                CollectionUser.collection_id == default_collection.collection_id,
                CollectionUser.user_id == plugin_user.user_id
            ).first()
            if not plugin_membership:
                db.add(CollectionUser(
                    collection_id=default_collection.collection_id,
                    user_id=plugin_user.user_id,
                    role="plugin",
                    can_upload=False,
                    can_download=True,
                    can_delete=False,
                    assigned_by=super_admin.user_id if existing_super_admin else user_admin.user_id,
                ))
                logging.info("✅ Linked plugin user to default collection")

            db.commit()

            logging.info("✅ User system initialized:")
            logging.info("   - Super Admin: superadmin/superadmin123 (global access)")
            logging.info("   - Admin: admin/admin123 (admin access)")
            logging.info("   - Plugin User: pluginuser/plugin123 (per-collection plugin access)")
            logging.info("   - Regular User: user/user123 (regular access)")

        finally:
            db.close()

    except Exception as e:
        logging.error(f"❌ Failed to initialize user system: {e}")
        # Don't raise here to avoid blocking startup


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


# Health check endpoint
@api_router.get("/health", tags=["Health"])
async def health_check():
    try:
        health_service = HealthMonitorService()
        return health_service.get_system_overview()
    except Exception as exc:
        logging.error(f"Health check failed: {exc}")
        return {"overall_status": "unhealthy", "error": str(exc)}


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to the Knowledge Base Chatbot API!"}


@api_router.post("/auth/token")
async def login_for_access_token(
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    json_body: Optional[TokenRequest] = Body(None),
):
    # Try to get credentials from either form data or JSON body
    final_username = username or (json_body.username if json_body else None)
    final_password = password or (json_body.password if json_body else None)

    if not final_username or not final_password:
        raise HTTPException(
            status_code=422,
            detail="Username and password are required",
        )

    token = get_token_from_credentials(final_username, final_password)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return JSONResponse(
        content={
            "access_token": token,
            "token_type": "bearer",
        }
    )


# Development server runner
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
