# app/api/routes_chat.py

from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.rag import RAG
from app.core.vector_singleton import get_vector_store
from app.core.database import get_db
from app.config import settings
from app.api.routes_auth import get_current_user
from app.utils.prompt_guard import is_safe_prompt
from app.services.chat_tracking import ChatTrackingService
from app.services.activity_tracker import activity_tracker
import redis
import logging
import json
import time

# Initialize FastAPI router
router = APIRouter()

# Initialize logger
logger = logging.getLogger("chat_logger")
logging.basicConfig(level=logging.INFO)

# Initialize RAG with singleton vector store
vector_store = get_vector_store()
rag = RAG(vector_store)

# Initialize services
chat_service = ChatTrackingService()

# Initialize Redis if enabled
r = None
if settings.USE_REDIS:
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)

# Request / Response models
class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    question: str
    top_k: int = 5  # optional, number of chunks to retrieve
    session_id: Optional[str] = None  # optional, for session tracking
    conversation_history: List[ConversationMessage] = []  # optional, for context
    maintain_context: bool = False  # optional, flag to maintain context

class ChatResponse(BaseModel):
    answer: str
    session_id: Optional[str] = None


# Chat endpoint
@router.post("/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    question = request.question.strip()
    top_k = request.top_k
    session_id = request.session_id
    conversation_history = request.conversation_history
    maintain_context = request.maintain_context

    # Validate question
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Prompt guard
    if not is_safe_prompt(question):
        raise HTTPException(status_code=400, detail="Unsafe or disallowed question detected")

    # Validate top_k
    if top_k <= 0 or top_k > 20:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 20")
    
    # Log context information
    logger.info(f"[CONTEXT] Session: {session_id}, Maintain: {maintain_context}, History: {len(conversation_history)} messages")
    
    # Create or get chat session for tracking
    if session_id:
        chat_service.create_or_get_session(session_id, current_user["username"], db)
    
    # Start timing for performance tracking
    start_time = time.time()

    # Check Redis cache first
    cache_key = f"faq:{question.lower()}"
    if r:
        cached_answer = r.get(cache_key)
        if cached_answer:
            answer_text = cached_answer.decode("utf-8")
            logger.info(f"[CACHE HIT] User: {current_user['username']}, Question: {question}")
            return ChatResponse(answer=answer_text, session_id=session_id)

    # Call RAG pipeline with debugging
    logger.info(f"[RAG QUERY] User: {current_user['username']}, Question: {question}, top_k: {top_k}")

    # Get chunks from vector store with debug info
    vector_store = get_vector_store()
    chunks = rag.retrieve_chunks(question, top_k=top_k)
    logger.info(f"[CHAT DEBUG] Retrieved {len(chunks)} chunks for query: {question}")
    logger.info(f"[CHAT DEBUG] Vector store type: {'Qdrant' if vector_store.client else 'In-memory fallback'}")

    if vector_store.client is None:
        logger.info(f"[CHAT DEBUG] Fallback storage has {len(vector_store.documents)} documents")

    if not chunks:
        logger.warning(f"[CHAT DEBUG] No chunks found for query: {question}")
        return ChatResponse(answer="I wasn't able to retrieve a confident answer, please refine your question.", session_id=session_id)

    # Generate answer with or without context
    try:
        if maintain_context and conversation_history:
            logger.info(f"[CONTEXT] Using context with {len(conversation_history)} messages")
            answer_text = rag.answer_with_context(question, conversation_history, top_k=top_k)
        else:
            logger.info(f"[CONTEXT] Using basic RAG without context")
            answer_text = rag.answer(question, top_k=top_k)
    except Exception as e:
        logger.error(f"[RAG ERROR] Failed to generate answer: {str(e)}")
        return ChatResponse(answer="I encountered an error while processing your question. Please try again.", session_id=session_id)

    # Store in Redis
    if r:
        r.set(cache_key, answer_text, ex=60*60*24)  # TTL 24 hours
        logger.info(f"[CACHE STORE] User: {current_user['username']}, Question: {question}")

    # Calculate processing time
    processing_time = int((time.time() - start_time) * 1000)  # milliseconds
    
    # Log query and answer
    logger.info(f"User: {current_user['username']}, Question: {question}, Answer: {answer_text}")
    
    # Track the query in database
    if session_id:
        try:
            context_info = {
                "chunks_retrieved": len(chunks),
                "maintain_context": maintain_context,
                "conversation_history_length": len(conversation_history),
                "top_k": top_k
            }
            chat_service.log_query(
                session_id=session_id,
                user_query=question,
                ai_response=answer_text,
                context_used=context_info,
                processing_time_ms=processing_time,
                db=db
            )
        except Exception as e:
            logger.error(f"Failed to track query: {str(e)}")

    # Log activity for activity tracker
    try:
        # Log chat session start if this is a new session
        if session_id and not conversation_history:
            activity_tracker.log_activity(
                activity_type="chat_session_start",
                user=current_user["username"],
                details={
                    "session_id": session_id,
                    "first_question": question[:100]  # First 100 chars
                }
            )
        
        # Log every chat query
        activity_tracker.log_activity(
            activity_type="chat_query",
            user=current_user["username"],
            details={
                "question": question[:100],  # First 100 chars
                "session_id": session_id,
                "chunks_retrieved": len(chunks),
                "processing_time_ms": processing_time,
                "has_context": maintain_context and len(conversation_history) > 0
            },
            metadata={
                "cache_hit": False,  # We already returned if cache hit
                "vector_db_type": "qdrant" if vector_store.client else "in_memory"
            }
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {str(e)}")

    return ChatResponse(answer=answer_text, session_id=session_id)


# Debug endpoint for search testing
@router.post("/debug/search")
async def debug_search(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Debug endpoint to test document retrieval"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admin users can access debug search")
    
    question = request.question.strip()
    top_k = request.top_k
    
    # Get chunks from vector store
    vector_store = get_vector_store()
    rag_instance = RAG(vector_store)
    chunks = rag_instance.retrieve_chunks(question, top_k=top_k)
    
    return {
        "query": question,
        "top_k": top_k,
        "chunks_found": len(chunks),
        "chunks": chunks[:3] if chunks else [],  # Return first 3 chunks for debugging
        "vector_db_type": "qdrant" if vector_store.client else "in_memory_fallback"
    }


# Chat Analytics Endpoints
@router.get("/analytics")
async def get_chat_analytics(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get chat analytics (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    analytics = chat_service.get_chat_analytics(db)
    return analytics


@router.get("/sessions")
async def get_user_sessions(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's chat sessions"""
    sessions = chat_service.get_user_sessions(current_user["username"], db)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get chat history for a specific session"""
    history = chat_service.get_session_history(session_id, db)
    return {"session_id": session_id, "history": history}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a chat session"""
    success = chat_service.delete_session(session_id, db)
    if success:
        return {"message": f"Session {session_id} deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")
