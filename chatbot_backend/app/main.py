# app/main.py

from fastapi import FastAPI, Request, Form, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.api import routes_auth, routes_files, routes_chat, routes_health, routes_activity
from app.core.database import init_database
from app.config import settings
from app.core.auth import get_token_from_credentials
import logging

class TokenRequest(BaseModel):
    username: str
    password: str

# Initialize FastAPI
app = FastAPI(
    title="Knowledge Base Chatbot API",
    description="Backend API for RAG + Claude chatbot with Qdrant vector DB",
    version="0.1.0",
)

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

# Include routers
app.include_router(routes_auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(routes_files.router, prefix="/files", tags=["Files"])
app.include_router(routes_chat.router, prefix="/chat", tags=["Chat"])
app.include_router(routes_health.router, prefix="/system", tags=["Health & Monitoring"])
app.include_router(routes_activity.router, prefix="/activity", tags=["Activity Tracking"])

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database and other startup tasks"""
    try:
        init_database()
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize database: {str(e)}")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
    )

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "mode": settings.APP_MODE}

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to the Knowledge Base Chatbot API!"}

@app.post("/auth/token")
async def login_for_access_token(
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    json_body: Optional[TokenRequest] = Body(None)
):
    # Try to get credentials from either form data or JSON body
    final_username = username or (json_body.username if json_body else None)
    final_password = password or (json_body.password if json_body else None)

    if not final_username or not final_password:
        raise HTTPException(
            status_code=422,
            detail="Username and password are required"
        )

    token = get_token_from_credentials(final_username, final_password)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return JSONResponse(content={
        "access_token": token,
        "token_type": "bearer"
    })

# Development server runner
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
