# app/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api import routes_auth, routes_files, routes_chat

# Initialize FastAPI
app = FastAPI(
    title="Knowledge Base Chatbot API",
    description="Backend API for RAG + Claude chatbot with Qdrant vector DB",
    version="0.1.0",
)

# CORS (allow frontend integration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to specific frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes_auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(routes_files.router, prefix="/files", tags=["Files"])
app.include_router(routes_chat.router, prefix="/chat", tags=["Chat"])

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

# Development server runner
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
