# app/api/routes_chat.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.rag import RAG
from app.core.vectorstore import VectorStore
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

# Initialize vector store and RAG
vector_store = VectorStore(settings.VECTOR_DB_URL)
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
async def ask_question(request: ChatRequest, current_user: str = Depends(get_current_user)):
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
            logger.info(f"[CACHE HIT] User: {current_user}, Question: {question}")
            return ChatResponse(answer=answer_text)

    # Call RAG pipeline
    answer_text = rag.answer(question, top_k=top_k)

    # Store in Redis
    if r:
        r.set(cache_key, answer_text, ex=60*60*24)  # TTL 24 hours
        logger.info(f"[CACHE STORE] User: {current_user}, Question: {question}")

    # Log query and answer
    logger.info(f"User: {current_user}, Question: {question}, Answer: {answer_text}")

    return ChatResponse(answer=answer_text)
