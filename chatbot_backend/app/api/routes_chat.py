# app/api/routes_chat.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.rag import RAG
from app.core.vector_singleton import get_vector_store
from app.config import settings
from app.api.routes_auth import get_current_user
from app.utils.prompt_guard import is_safe_prompt
import redis
import logging
import json

# Initialize FastAPI router
router = APIRouter()

# Initialize logger
logger = logging.getLogger("chat_logger")
logging.basicConfig(level=logging.INFO)

# Initialize RAG with singleton vector store
vector_store = get_vector_store()
rag = RAG(vector_store)

# Initialize Redis if enabled
r = None
if settings.USE_REDIS:
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)

# Request / Response models
class ChatRequest(BaseModel):
    question: str
    top_k: int = 5  # optional, number of chunks to retrieve


class ChatResponse(BaseModel):
    answer: str


# Chat endpoint
@router.post("/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    question = request.question.strip()
    top_k = request.top_k

    # Validate question
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Prompt guard
    if not is_safe_prompt(question):
        raise HTTPException(status_code=400, detail="Unsafe or disallowed question detected")

    # Validate top_k
    if top_k <= 0 or top_k > 20:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 20")

    # Check Redis cache first
    cache_key = f"faq:{question.lower()}"
    if r:
        cached_answer = r.get(cache_key)
        if cached_answer:
            answer_text = cached_answer.decode("utf-8")
            logger.info(f"[CACHE HIT] User: {current_user['username']}, Question: {question}")
            return ChatResponse(answer=answer_text)

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
        return {"answer": "I wasn't able to retrieve a confident answer, please refine your question."}

    answer_text = rag.answer(question, top_k=top_k)

    # Store in Redis
    if r:
        r.set(cache_key, answer_text, ex=60*60*24)  # TTL 24 hours
        logger.info(f"[CACHE STORE] User: {current_user['username']}, Question: {question}")

    # Log query and answer
    logger.info(f"User: {current_user['username']}, Question: {question}, Answer: {answer_text}")

    return ChatResponse(answer=answer_text)


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
