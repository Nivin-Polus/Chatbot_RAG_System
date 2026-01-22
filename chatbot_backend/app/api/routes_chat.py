# app/api/routes_chat.py

from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.config import settings
from app.api.routes_auth import (
    get_current_user,
    normalize_domain,
    find_collection_by_domain,
    ensure_public_user,
)
from app.utils.prompt_guard import is_safe_prompt
from app.services.chat_tracking import ChatTrackingService
from app.services.activity_tracker import activity_tracker
from app.utils.chat_history_logger import log_chat_interaction
from app.models.collection import Collection, CollectionUser
from app.models.query_log import QueryLog
from app.utils.rate_limiter import rate_limiter
import logging
import json
import time
import uuid
import re

# Initialize FastAPI router
router = APIRouter()

# Initialize logger
logger = logging.getLogger("chat_logger")
logging.basicConfig(level=logging.INFO)

# Initialize services
chat_service = ChatTrackingService()

# Request / Response models
class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    question: str
    top_k: int = 12  # optional, number of chunks to retrieve
    session_id: Optional[str] = None  # optional, for session tracking
    conversation_history: List[ConversationMessage] = []  # optional, for context
    maintain_context: bool = False  # optional, flag to maintain context
    collection_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: Optional[str] = None  # Made optional for follow-up responses
    session_id: Optional[str] = None
    is_generic: bool = False
    is_followup: bool = False  # NEW: Indicates this is a follow-up question
    followup_questions: Optional[str] = None  # NEW: The follow-up question text
    followup_reason: Optional[str] = None  # NEW: Reason for follow-up
    sources: Optional[List[Dict]] = None
    chunk_count: int = 0  # NEW: Number of chunks retrieved


class PublicChatRequest(ChatRequest):
    website_url: str


def _is_generic_query(question: str) -> bool:
    """Check if the question is a generic greeting or small talk."""
    if not question:
        return False
    
    normalized = question.strip().lower()
    # Remove punctuation for better matching
    normalized = normalized.rstrip("!?.,")
    
    small_talk_phrases = {
        "hi", "hello", "hey", "hi there", "hello there",
        "good morning", "good evening", "good afternoon",
        "how are you", "how are you doing", "what's up", "whats up",
        "thanks", "thank you", "bye", "goodbye", "see you",
        "ok", "okay", "cool", "nice", "great",
    }
    
    return normalized in small_talk_phrases


def _is_generic_response(answer: str) -> bool:
    """Check if the answer indicates inability to help or is a generic greeting response."""
    if not answer:
        return False
    
    normalized = answer.strip().lower()
    
    # Patterns indicating "I don't know" type responses
    generic_patterns = [
        "i wasn't able to retrieve",
        "i wasn't able to find",
        "i couldn't find",
        "i don't have information",
        "i don't have enough information",
        "i don't have any information",
        "i do not have any information",
        "i do not have information",
        "i cannot find",
        "unfortunately, i don't",
        "unfortunately i don't",
        "i'm not able to",
        "i am not able to",
        "i'm unable to",
        "i am unable to",
        "no relevant information",
        "please refine your question",
        "could you clarify",
        "could you provide more",
        "i'm here to help with questions about your knowledge base",
        "let me know what you'd like to learn",
        # Patterns for "no information in context" responses
        "the provided context does not contain",
        "does not contain any information",
        "do not have enough details",
        "do not have enough context",
        "without any relevant information",
        "there are no sources that discuss",
        "i do not have enough details to provide",
        "my role is to assist based on the provided information",
        # Apology patterns for inability to answer
        "i apologize, but i do not have",
        "i apologize but i do not have",
        "i apologize, but i don't have",
        "i apologize but i don't have",
        "is not relevant to answering",
        "that is relevant to answering",
    ]
    
    for pattern in generic_patterns:
        if pattern in normalized:
            return True
    
    return False


def _process_chat_request(
    *,
    question: str,
    top_k: int,
    session_id: Optional[str],
    conversation_history: List[ConversationMessage],
    maintain_context: bool,
    collection_id: Optional[str],
    identity: Dict,
    db: Session,
) -> ChatResponse:
    question = (question or "").strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not is_safe_prompt(question):
        raise HTTPException(status_code=400, detail="Unsafe or disallowed question detected")

    if top_k <= 0 or top_k > 20:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 20")

    identity_username = identity.get("username", "anonymous")
    user_role = identity.get("role", "user")
    user_id = identity.get("user_id") or identity_username

    # Determine accessible collections for the requesting user (non super-admin)
    accessible_collection_ids: set[str] = set()
    if user_role != "super_admin" and user_id:
        # Collections the user explicitly belongs to
        membership_ids = (
            db.query(CollectionUser.collection_id)
            .filter(CollectionUser.user_id == user_id)
            .all()
        )
        accessible_collection_ids.update(str(row[0]) for row in membership_ids if row[0])

        # Collections the user administers
        admin_ids = (
            db.query(Collection.collection_id)
            .filter(Collection.admin_user_id == user_id)
            .all()
        )
        accessible_collection_ids.update(str(row[0]) for row in admin_ids if row[0])

        # Include identity-provided collection hints
        identity_collection_ids = identity.get("collection_ids") or []
        if isinstance(identity_collection_ids, list):
            accessible_collection_ids.update(str(cid) for cid in identity_collection_ids if cid)
        identity_single_collection = identity.get("collection_id")
        if identity_single_collection:
            accessible_collection_ids.add(str(identity_single_collection))

    # Resolve effective collection selection with access enforcement
    effective_collection_id = collection_id or identity.get("collection_id")
    if user_role != "super_admin":
        if not accessible_collection_ids:
            raise HTTPException(status_code=403, detail="You do not have access to any knowledge bases.")

        if effective_collection_id:
            if str(effective_collection_id) not in accessible_collection_ids:
                raise HTTPException(status_code=403, detail="Access denied to the requested knowledge base.")
        else:
            # Default to the first accessible collection if none specified
            effective_collection_id = next(iter(accessible_collection_ids))

    effective_session_id = session_id or identity.get("session_id") or str(uuid.uuid4())

    logger.info(
        f"[CONTEXT] Session: {effective_session_id}, Maintain: {maintain_context}, "
        f"History: {len(conversation_history)} messages"
    )

    if effective_session_id and user_id:
        chat_service.create_or_get_session(effective_session_id, user_id, effective_collection_id, db)

    start_time = time.time()

    logger.debug(f"[RAG QUERY] User: {identity_username}, Question: {question}, top_k: {top_k}")

    # Import here to avoid PyO3 initialization issues during module import
    from app.core.vector_singleton import get_vector_store
    from app.core.rag import RAG
    
    vector_store = get_vector_store()
    rag_instance = RAG(db_session=db)
    chunks = rag_instance.retrieve_chunks(question, top_k=top_k, collection_id=effective_collection_id)
    logger.debug(f"[CHAT DEBUG] Retrieved {len(chunks)} chunks for query: {question}")
    logger.debug(f"[CHAT DEBUG] Vector store type: {'Qdrant' if vector_store.client else 'In-memory fallback'}")

    if vector_store.client is None:
        logger.debug(f"[CHAT DEBUG] Fallback storage has {len(vector_store.documents)} documents")

    source_records: dict[str, dict] = {}
    for chunk in chunks:
        file_id = chunk.get("file_id")
        file_name = chunk.get("file_name") or "Unknown File"
        chunk_index = chunk.get("chunk_index")
        chunk_score = chunk.get("score", 0.0)  # Get confidence score
        # Get source type and URL for web crawl sources
        source_type = chunk.get("source_type", "file")
        url = chunk.get("url") or chunk.get("canonical_url", "")

        record_key = file_id or file_name
        if not record_key:
            continue

        record = source_records.get(record_key)
        if not record:
            record = {
                "file_name": file_name,
                "file_id": file_id,
                "chunk_indices": [],
                "source_type": source_type,
                "url": url,
                "max_score": chunk_score,  # Track max confidence score for this source
                "scores": [chunk_score],  # Track all scores for averaging if needed
            }
            source_records[record_key] = record
        else:
            # Update max score if this chunk has higher confidence
            record["max_score"] = max(record.get("max_score", 0.0), chunk_score)
            record["scores"].append(chunk_score)

        if chunk_index is not None:
            record["chunk_indices"].append(chunk_index)

    # Import settings for SOURCE_MIN_SCORE threshold
    from app.config import settings
    source_min_score = getattr(settings, "SOURCE_MIN_SCORE", 0.35)
    
    sources_payload = []
    filtered_sources_count = 0
    
    for record in source_records.values():
        max_score = record.get("max_score", 0.0)
        
        # Filter out sources below confidence threshold
        if max_score < source_min_score:
            filtered_sources_count += 1
            logger.info(f"[SOURCE FILTER] Excluding '{record.get('file_name')}' (score: {max_score:.4f} < threshold: {source_min_score})")
            continue
        
        payload = {
            "file_name": record.get("file_name", "Unknown File"),
            "confidence": round(max_score, 4),  # Add confidence score to payload
        }
        if record.get("file_id"):
            payload["file_id"] = record["file_id"]
        if record.get("chunk_indices"):
            payload["chunk_indices"] = record["chunk_indices"]
        # Add source_type and url for web crawl sources
        if record.get("source_type"):
            payload["source_type"] = record["source_type"]
        if record.get("url"):
            payload["url"] = record["url"]
        sources_payload.append(payload)
    
    if filtered_sources_count > 0:
        logger.info(f"[SOURCE FILTER] Filtered out {filtered_sources_count} low-confidence sources (threshold: {source_min_score})")

    # Step 2: Check if follow-up is needed (BEFORE answer generation)
    needs_followup, followup_reason = rag_instance.needs_followup(
        question=question,
        chunks=chunks
    )
    
    # Step 3: If follow-up needed, generate and return early
    if needs_followup:
        followup_text = rag_instance.generate_followup_questions(
            question=question,
            chunks=chunks,
            reason=followup_reason
        )
        
        # Log the follow-up event
        try:
            activity_tracker.log_activity(
                activity_type="chat_followup_triggered",
                user=identity_username,
                details={
                    "question": question[:100],
                    "reason": followup_reason,
                    "chunk_count": len(chunks),
                    "session_id": effective_session_id
                }
            )
        except Exception as e:
            logger.error(f"Failed to log follow-up activity: {str(e)}")
        
        logger.info(f"[FOLLOWUP RESPONSE] Returning follow-up for reason: {followup_reason}")
        
        # Return follow-up response (SKIP answer generation)
        return ChatResponse(
            answer=None,
            session_id=effective_session_id,
            is_followup=True,
            followup_questions=followup_text,
            followup_reason=followup_reason,
            sources=[],
            chunk_count=len(chunks)
        )

    try:
        if maintain_context and conversation_history:
            logger.debug(f"[CONTEXT] Using context with {len(conversation_history)} messages")
            rag_result = rag_instance.answer_with_context(
                question,
                conversation_history,
                top_k=top_k,
                collection_id=effective_collection_id,
            )
        else:
            logger.debug("[CONTEXT] Using basic RAG without context")
            rag_result = rag_instance.answer(
                question,
                top_k=top_k,
                collection_id=effective_collection_id,
            )
        
        # Handle new dict return format from RAG (contains 'answer' and 'is_generic')
        tokens_used = None
        model_name = None
        if isinstance(rag_result, dict):
            answer_text = rag_result.get("answer", "")
            is_generic_from_ai = rag_result.get("is_generic", False)
            tokens_used = rag_result.get("tokens_used")
            model_name = rag_result.get("model_name")
        else:
            # Fallback for string return (shouldn't happen with updated RAG)
            answer_text = rag_result
            is_generic_from_ai = _is_generic_query(question) or _is_generic_response(answer_text)
        
        # If model_name not in rag_result, get from settings
        if not model_name:
            from app.config import settings
            if settings.AI_PROVIDER == "bedrock":
                model_name = settings.AWS_MODEL
            else:
                model_name = settings.CLAUDE_MODEL
        
        # Safety check: Remove any "Sources:" section from answer text (should be in sources field only)
        # Use word boundary \b to avoid matching "Sources" inside words like "resources"
        # Require newline or start of string, optional markdown formatting, then "Sources:" as a header
        answer_text = re.sub(r'(?:^|\n)\s*\**\s*\bSources?\b:?\s*\**\s*(?:\n[\s\S]*)?$', '', answer_text, flags=re.IGNORECASE).strip()
        
    except Exception as e:
        logger.error(f"[RAG ERROR] Failed to generate answer: {str(e)}")
        return ChatResponse(
            answer="I encountered an error while processing your question. Please try again.",
            session_id=effective_session_id,
            is_generic=True,
            sources=sources_payload,
        )

    processing_time = int((time.time() - start_time) * 1000)

    logger.debug(f"User: {identity_username}, Question: {question}, Answer: {answer_text}")

    context_info = {
        "chunks_retrieved": len(chunks),
        "maintain_context": maintain_context,
        "conversation_history_length": len(conversation_history),
        "top_k": top_k,
    }

    if effective_session_id:
        try:
            chat_service.log_query(
                session_id=effective_session_id,
                collection_id=effective_collection_id,
                user_query=question,
                ai_response=answer_text,
                context_used=context_info,
                processing_time_ms=processing_time,
                db=db,
            )
        except Exception as e:
            logger.error(f"Failed to track query: {str(e)}")

    # Log token and query usage into QueryLog for analytics
    try:
        website_id = identity.get("website_id")

        # For super admins or contexts without website_id, derive it from the collection
        if not website_id and effective_collection_id:
            try:
                collection_obj = (
                    db.query(Collection)
                    .filter(Collection.collection_id == effective_collection_id)
                    .first()
                )
                if collection_obj and getattr(collection_obj, "website_id", None):
                    website_id = collection_obj.website_id
            except Exception as e:
                logger.error(f"Failed to resolve website_id from collection {effective_collection_id}: {e}")
        
        # Fallback: If website_id is still None, try to find a default one to ensure logging works
        if not website_id:
            try:
                from app.models.website import Website
                # Try specific default first, then any
                fallback_site = db.query(Website).filter(Website.domain == "default.local").first()
                if not fallback_site:
                    fallback_site = db.query(Website).first()
                
                if fallback_site:
                    website_id = fallback_site.website_id
                    logger.info(f"Using fallback website_id {website_id} for logging")
            except Exception as e:
                logger.error(f"Failed to resolve fallback website_id: {e}")

        if website_id and user_id:
            # Build list of accessed file IDs from sources
            file_ids = [
                s.get("file_id")
                for s in sources_payload or []
                if isinstance(s, dict) and s.get("file_id")
            ]

            ql = QueryLog(
                user_id=user_id,
                website_id=website_id,
                session_id=effective_session_id,
                user_query=question,
                ai_response=answer_text,
                query_type="chat",
                processing_time_ms=processing_time,
                tokens_used=tokens_used,
                chunks_retrieved=len(chunks),
                model_name=model_name,
                status="success",
            )

            # Attach context and files metadata using helpers
            if context_info:
                ql.set_context_data(context_info)
            if file_ids:
                ql.set_files_accessed_list(file_ids)

            db.add(ql)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to log query usage: {str(e)}")
        db.rollback()

    try:
        if effective_session_id and not conversation_history:
            activity_tracker.log_activity(
                activity_type="chat_session_start",
                user=identity_username,
                details={
                    "session_id": effective_session_id,
                    "first_question": question[:100],
                },
            )

        activity_tracker.log_activity(
            activity_type="chat_query",
            user=identity_username,
            details={
                "question": question[:100],
                "session_id": effective_session_id,
                "chunks_retrieved": len(chunks),
                "processing_time_ms": processing_time,
                "has_context": maintain_context and len(conversation_history) > 0,
            },
            metadata={
                "vector_db_type": "qdrant" if vector_store.client else "in_memory",
            },
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {str(e)}")

    # Log chat interaction to daily rotating file
    try:
        log_chat_interaction(
            session_id=effective_session_id,
            user_id=user_id or "anonymous",
            username=identity_username,
            role=user_role,
            collection_id=effective_collection_id,
            question=question,
            answer=answer_text,
            processing_time_ms=processing_time,
            chunks_retrieved=len(chunks),
            sources=sources_payload,
        )
    except Exception as e:
        logger.error(f"Failed to log chat history to file: {str(e)}")

    # Use AI-provided is_generic flag (set by RAG via classification instruction in prompt)
    # Falls back to regex-based detection only if RAG returned a string (legacy behavior)
    is_generic = is_generic_from_ai
    
    # Don't send sources for generic responses
    if is_generic:
        sources_payload = []
    
    # Debug: Log final response being sent to frontend
    logger.info(f"[API RESPONSE] Final answer length: {len(answer_text)} chars")
    logger.info(f"[API RESPONSE] Final answer content:\n{answer_text}")
    logger.info(f"[API RESPONSE] is_generic: {is_generic}, sources count: {len(sources_payload)}")
    
    return ChatResponse(answer=answer_text, session_id=effective_session_id, is_generic=is_generic, sources=sources_payload, chunk_count=len(chunks))


# Chat endpoint
@router.post(
    "/ask",
    response_model=ChatResponse,
    dependencies=[Depends(rate_limiter(limit=60, window_seconds=60))],
)
async def ask_question(request: ChatRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    resolved_collection_id = request.collection_id or current_user.get("collection_id")
    resolved_session_id = request.session_id or current_user.get("session_id")

    return _process_chat_request(
        question=request.question,
        top_k=request.top_k,
        session_id=resolved_session_id,
        conversation_history=request.conversation_history,
        maintain_context=request.maintain_context,
        collection_id=resolved_collection_id,
        identity=current_user,
        db=db,
    )


@router.post(
    "/public/ask",
    response_model=ChatResponse,
    dependencies=[Depends(rate_limiter(limit=120, window_seconds=60))],
)
async def public_chat(request: PublicChatRequest, db: Session = Depends(get_db)):
    domain = normalize_domain(request.website_url)

    if not domain:
        raise HTTPException(status_code=400, detail="Invalid website URL provided")

    collection = find_collection_by_domain(domain, db)

    if not collection:
        raise HTTPException(status_code=404, detail="No collection is mapped to this website")

    if not collection.is_active:
        raise HTTPException(status_code=403, detail="Collection is inactive")

    public_user = ensure_public_user(collection, db)
    db.commit()

    resolved_session_id = request.session_id or str(uuid.uuid4())

    identity = {
        "username": public_user.username,
        "role": public_user.role,
        "user_id": public_user.user_id,
        "website_id": public_user.website_id,
        "collection_id": collection.collection_id,
        "auth_type": "public",
        "session_id": resolved_session_id,
    }

    return _process_chat_request(
        question=request.question,
        top_k=request.top_k,
        session_id=resolved_session_id,
        conversation_history=request.conversation_history,
        maintain_context=request.maintain_context,
        collection_id=collection.collection_id,
        identity=identity,
        db=db,
    )


# Debug endpoint for search testing
@router.post("/debug/search")
async def debug_search(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Debug endpoint to test document retrieval"""
    if current_user.get("role") not in ["super_admin", "user_admin"]:
        raise HTTPException(status_code=403, detail="Only admin users can access debug search")
    
    question = request.question.strip()
    top_k = request.top_k
    
    # Get chunks from vector store
    # Import here to avoid PyO3 initialization issues during module import
    from app.core.vector_singleton import get_vector_store
    from app.core.rag import RAG
    
    vector_store = get_vector_store()
    rag_instance = RAG()
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
    if current_user.get("role") not in ["super_admin", "user_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    analytics = chat_service.get_chat_analytics(db)
    return analytics


@router.get("/sessions")
async def get_user_sessions(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's chat sessions"""
    # Get accessible collections for the user
    accessible_collection_ids = None
    
    if current_user.get("role") == "super_admin":
        # Super admin can see all sessions
        accessible_collection_ids = None
    else:
        # Get collections the user has access to
        from app.models.collection import Collection, CollectionUser
        
        if current_user.get("role") == "user_admin":
            # User admin can see sessions from collections they admin
            collections = db.query(Collection).filter(
                Collection.admin_user_id == current_user["user_id"]
            ).all()
        else:
            # Regular user can only see sessions from collections they're members of
            collections = db.query(Collection).join(CollectionUser).filter(
                CollectionUser.user_id == current_user["user_id"]
            ).all()
        
        accessible_collection_ids = [c.collection_id for c in collections]
    
    sessions = chat_service.get_user_sessions(
        current_user["user_id"], 
        db, 
        accessible_collection_ids=accessible_collection_ids
    )
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get chat history for a specific session"""
    # Check if user has access to this session
    from app.models.chat_tracking import ChatSession
    from app.models.collection import Collection, CollectionUser
    
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check permissions
    if current_user.get("role") != "super_admin":
        # Check if user owns the session
        if session.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if user has access to the collection
        if session.collection_id:
            if current_user.get("role") == "user_admin":
                # User admin must be admin of the collection
                collection = db.query(Collection).filter(
                    Collection.collection_id == session.collection_id,
                    Collection.admin_user_id == current_user["user_id"]
                ).first()
                if not collection:
                    raise HTTPException(status_code=403, detail="Access denied to collection")
            else:
                # Regular user must be member of the collection
                membership = db.query(CollectionUser).filter(
                    CollectionUser.collection_id == session.collection_id,
                    CollectionUser.user_id == current_user["user_id"]
                ).first()
                if not membership:
                    raise HTTPException(status_code=403, detail="Access denied to collection")
    
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


@router.post("/history/save")
async def save_chat_history(
    request: Dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save full chat history (all messages) for a session"""
    from app.models.chat_tracking import ChatSession
    from app.models.collection import Collection, CollectionUser
    
    session_id = request.get("session_id")
    collection_id = request.get("collection_id")
    messages = request.get("messages", [])
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be a list")
    
    user_id = current_user.get("user_id")
    user_role = current_user.get("role")
    
    # Check permissions
    if user_role != "super_admin":
        # Verify session belongs to user or user has access to collection
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if session:
            if session.user_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied")
            
            if collection_id and session.collection_id != collection_id:
                # Verify user has access to the collection
                if user_role == "user_admin":
                    collection = db.query(Collection).filter(
                        Collection.collection_id == collection_id,
                        Collection.admin_user_id == user_id
                    ).first()
                    if not collection:
                        raise HTTPException(status_code=403, detail="Access denied to collection")
                else:
                    membership = db.query(CollectionUser).filter(
                        CollectionUser.collection_id == collection_id,
                        CollectionUser.user_id == user_id
                    ).first()
                    if not membership:
                        raise HTTPException(status_code=403, detail="Access denied to collection")
    
    success = chat_service.save_chat_history(session_id, user_id, collection_id, messages, db)
    if success:
        return {"message": "Chat history saved successfully", "session_id": session_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to save chat history")


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full chat history (all messages) for a session"""
    from app.models.chat_tracking import ChatSession
    from app.models.collection import Collection, CollectionUser
    
    # Check if session exists
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    user_id = current_user.get("user_id")
    user_role = current_user.get("role")
    
    # Check permissions
    if user_role != "super_admin":
        # Check if user owns the session
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if user has access to the collection
        if session.collection_id:
            if user_role == "user_admin":
                collection = db.query(Collection).filter(
                    Collection.collection_id == session.collection_id,
                    Collection.admin_user_id == user_id
                ).first()
                if not collection:
                    raise HTTPException(status_code=403, detail="Access denied to collection")
            else:
                membership = db.query(CollectionUser).filter(
                    CollectionUser.collection_id == session.collection_id,
                    CollectionUser.user_id == user_id
                ).first()
                if not membership:
                    raise HTTPException(status_code=403, detail="Access denied to collection")
    
    messages = chat_service.get_chat_history(session_id, db)
    return {"session_id": session_id, "messages": messages}


@router.delete("/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear chat history for a session (delete all messages)"""
    from app.models.chat_tracking import ChatSession
    from app.models.collection import Collection, CollectionUser
    
    # Check if session exists
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    user_id = current_user.get("user_id")
    user_role = current_user.get("role")
    
    # Check permissions
    if user_role != "super_admin":
        # Check if user owns the session
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if user has access to the collection
        if session.collection_id:
            if user_role == "user_admin":
                collection = db.query(Collection).filter(
                    Collection.collection_id == session.collection_id,
                    Collection.admin_user_id == user_id
                ).first()
                if not collection:
                    raise HTTPException(status_code=403, detail="Access denied to collection")
            else:
                membership = db.query(CollectionUser).filter(
                    CollectionUser.collection_id == session.collection_id,
                    CollectionUser.user_id == user_id
                ).first()
                if not membership:
                    raise HTTPException(status_code=403, detail="Access denied to collection")
    
    success = chat_service.clear_chat_history(session_id, db)
    if success:
        return {"message": "Chat history cleared successfully", "session_id": session_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear chat history")
