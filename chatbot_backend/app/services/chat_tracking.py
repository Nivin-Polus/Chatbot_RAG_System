from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.chat_tracking import ChatSession, ChatQuery, ChatMessageHistory
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

class ChatTrackingService:
    
    def create_or_get_session(self, session_id: str, user_id: str, collection_id: str | None, db: Session) -> ChatSession:
        """Create new session or get existing one"""
        try:
            # Try to get existing session
            session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            
            if not session:
                # Create new session
                session = ChatSession(
                    session_id=session_id,
                    user_id=user_id,
                    session_name=f"Chat Session {session_id[:8]}",
                    collection_id=collection_id
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                logger.info(f"Created new chat session: {session_id}")
            else:
                # Update collection association if provided and missing
                if collection_id and session.collection_id != collection_id:
                    session.collection_id = collection_id
                    db.commit()
                    db.refresh(session)
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to create/get session {session_id}: {str(e)}")
            db.rollback()
            raise
    
    def log_query(self, session_id: str, collection_id: str | None, user_query: str, ai_response: str,
                  context_used: Optional[Dict], processing_time_ms: Optional[int],
                  db: Session) -> ChatQuery:
        """Log a chat query and response"""
        try:
            # Create query record
            query = ChatQuery(
                session_id=session_id,
                user_query=user_query,
                ai_response=ai_response,
                context_used=context_used,
                processing_time_ms=str(processing_time_ms) if processing_time_ms else None,
                collection_id=collection_id
            )
            
            db.add(query)
            
            # Update session's updated_at and query count
            session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if session:
                try:
                    current_count = int(session.total_queries or 0)
                except (TypeError, ValueError):
                    current_count = 0
                session.total_queries = str(current_count + 1)
                if collection_id and session.collection_id != collection_id:
                    session.collection_id = collection_id
            
            db.commit()
            db.refresh(query)
            
            logger.info(f"Logged query for session {session_id}")
            return query
            
        except Exception as e:
            logger.error(f"Failed to log query for session {session_id}: {str(e)}")
            db.rollback()
            raise
    
    def get_session_history(self, session_id: str, db: Session, limit: int = 50) -> List[Dict]:
        """Get chat history for a session"""
        try:
            queries = db.query(ChatQuery).filter(
                ChatQuery.session_id == session_id
            ).order_by(ChatQuery.created_at.desc()).limit(limit).all()
            
            return [query.to_dict() for query in queries]
            
        except Exception as e:
            logger.error(f"Failed to get session history {session_id}: {str(e)}")
            return []
    
    def get_user_sessions(self, user_id: str, db: Session, limit: int = 20, accessible_collection_ids: List[str] = None) -> List[Dict]:
        """Get all sessions for a user, filtered by accessible collections"""
        try:
            query = db.query(ChatSession).filter(ChatSession.user_id == user_id)
            
            # Filter by accessible collections if provided
            if accessible_collection_ids is not None:
                if accessible_collection_ids:  # If user has access to some collections
                    query = query.filter(ChatSession.collection_id.in_(accessible_collection_ids))
                else:  # If user has no accessible collections, return empty
                    return []
            
            sessions = query.order_by(ChatSession.updated_at.desc()).limit(limit).all()
            
            return [session.to_dict() for session in sessions]
            
        except Exception as e:
            logger.error(f"Failed to get user sessions {user_id}: {str(e)}")
            return []
    
    def get_chat_analytics(self, db: Session, days: int = 30) -> Dict:
        """Get chat analytics for the last N days"""
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Total size
            total_size = db.query(ChatSession).with_entities(
                func.sum(ChatSession.total_queries)
            ).scalar() or 0
            
            # Get file type distribution
            file_types = db.query(
                ChatSession.session_name,
                func.count(ChatSession.session_id)
            ).group_by(ChatSession.session_name).all()
            
            # Active users (unique user_ids with sessions)
            active_users = db.query(ChatSession.user_id).filter(
                ChatSession.created_at >= cutoff_date
            ).distinct().count()
            
            # Total queries in period
            total_queries = db.query(ChatQuery).filter(
                ChatQuery.created_at >= cutoff_date
            ).count()
            
            # Total sessions in period
            total_sessions = db.query(ChatSession).filter(
                ChatSession.created_at >= cutoff_date
            ).count()
            
            # Average queries per session
            avg_queries_per_session = round(total_queries / total_sessions, 2) if total_sessions > 0 else 0
            
            # Most active users
            most_active = db.query(
                ChatSession.user_id,
                func.count(ChatQuery.query_id).label('query_count')
            ).join(ChatQuery).filter(
                ChatSession.created_at >= cutoff_date
            ).group_by(ChatSession.user_id).order_by(
                func.count(ChatQuery.query_id).desc()
            ).limit(5).all()
            
            return {
                "period_days": days,
                "total_queries": total_queries,
                "total_sessions": total_sessions,
                "active_users": active_users,
                "avg_queries_per_session": avg_queries_per_session,
                "most_active_users": [
                    {"user_id": user_id, "query_count": count} 
                    for user_id, count in most_active
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get chat analytics: {str(e)}")
            return {"error": str(e)}
    
    def delete_session(self, session_id: str, db: Session) -> bool:
        """Delete a chat session and all its queries"""
        try:
            session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
            if session:
                db.delete(session)  # Cascade will delete related queries and message history
                db.commit()
                logger.info(f"Deleted session: {session_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {str(e)}")
            db.rollback()
            return False
    
    def save_chat_history(self, session_id: str, user_id: str, collection_id: Optional[str], 
                         messages: List[Dict[str, Any]], db: Session) -> bool:
        """Save full chat history (all messages) for a session"""
        try:
            try:
                from dateutil import parser as dateutil_parser
            except ImportError:
                # Fallback to datetime if dateutil not available
                dateutil_parser = None
            
            # Ensure session exists
            session = self.create_or_get_session(session_id, user_id, collection_id, db)
            
            # Delete existing message history for this session
            db.query(ChatMessageHistory).filter(
                ChatMessageHistory.session_id == session_id
            ).delete()
            
            # Insert new messages with preserved timestamps and order
            for index, msg in enumerate(messages):
                # Parse timestamp from message
                msg_timestamp = None
                if msg.get("timestamp"):
                    try:
                        if isinstance(msg["timestamp"], str):
                            if dateutil_parser:
                                msg_timestamp = dateutil_parser.parse(msg["timestamp"])
                            else:
                                # Fallback to datetime.fromisoformat for ISO strings
                                msg_timestamp = datetime.fromisoformat(msg["timestamp"].replace('Z', '+00:00'))
                        elif isinstance(msg["timestamp"], datetime):
                            msg_timestamp = msg["timestamp"]
                    except Exception as e:
                        logger.warning(f"Could not parse timestamp for message {index}: {e}, using current time")
                        msg_timestamp = datetime.utcnow()
                
                # Use current time as fallback
                if not msg_timestamp:
                    msg_timestamp = datetime.utcnow()
                
                message = ChatMessageHistory(
                    original_message_id=msg.get("id"),  # Preserve original message ID
                    session_id=session_id,
                    collection_id=collection_id,
                    user_id=user_id,
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    sources=msg.get("sources"),
                    message_timestamp=msg_timestamp,  # Use original timestamp
                    message_order=index  # Store order in conversation
                )
                db.add(message)
            
            # Update session timestamp
            session.updated_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Saved {len(messages)} messages for session {session_id} in correct order")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save chat history for session {session_id}: {str(e)}")
            db.rollback()
            return False
    
    def get_chat_history(self, session_id: str, db: Session) -> List[Dict[str, Any]]:
        """Get full chat history (all messages) for a session in correct order"""
        try:
            # Order by message_order first (if available), then by message_timestamp, then by created_at
            # Use COALESCE to handle NULL values in ordering
            from sqlalchemy import case
            
            messages = db.query(ChatMessageHistory).filter(
                ChatMessageHistory.session_id == session_id
            ).order_by(
                case(
                    (ChatMessageHistory.message_order.is_(None), 999999),
                    else_=ChatMessageHistory.message_order
                ).asc(),
                ChatMessageHistory.message_timestamp.asc(),
                ChatMessageHistory.created_at.asc()
            ).all()
            
            return [msg.to_dict() for msg in messages]
            
        except Exception as e:
            logger.error(f"Failed to get chat history for session {session_id}: {str(e)}")
            return []
    
    def clear_chat_history(self, session_id: str, db: Session) -> bool:
        """Clear chat history for a session (delete all messages)"""
        try:
            deleted = db.query(ChatMessageHistory).filter(
                ChatMessageHistory.session_id == session_id
            ).delete()
            
            db.commit()
            logger.info(f"Cleared {deleted} messages for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear chat history for session {session_id}: {str(e)}")
            db.rollback()
            return False
