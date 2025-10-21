"""
Chat History Logger - Logs all chat interactions to daily rotating files
"""
import json
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

# Chat history log directory
CHAT_LOG_DIR = Path("storage/chat_logs")
CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Initialize logger
_chat_history_logger: Optional[logging.Logger] = None


def get_chat_history_logger() -> logging.Logger:
    """Get or create the chat history logger with daily rotation"""
    global _chat_history_logger
    
    if _chat_history_logger is not None:
        return _chat_history_logger
    
    # Create logger
    logger = logging.getLogger("chat_history")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    # Create handler with daily rotation
    log_file = CHAT_LOG_DIR / "chat_history.log"
    handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",  # Rotate at midnight
        interval=1,       # Every 1 day
        backupCount=30,   # Keep 30 days of logs
        encoding="utf-8",
    )
    
    # Set format to just log the JSON message
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    
    # Add handler if not already added
    if not logger.handlers:
        logger.addHandler(handler)
    
    _chat_history_logger = logger
    return logger


def log_chat_interaction(
    *,
    session_id: str,
    user_id: str,
    username: str,
    role: str,
    collection_id: Optional[str],
    question: str,
    answer: str,
    processing_time_ms: Optional[int] = None,
    chunks_retrieved: Optional[int] = None,
    sources: Optional[list] = None,
) -> None:
    """
    Log a chat interaction to the daily rotating file
    
    Args:
        session_id: Chat session identifier
        user_id: User ID
        username: Username
        role: User role (user, user_admin, super_admin)
        collection_id: Knowledge base collection ID
        question: User's question
        answer: AI's response
        processing_time_ms: Time taken to process (milliseconds)
        chunks_retrieved: Number of document chunks retrieved
        sources: List of source documents used
    """
    logger = get_chat_history_logger()
    
    # Extract only file names from sources
    source_file_names = []
    if sources:
        for source in sources:
            if isinstance(source, dict) and "file_name" in source:
                source_file_names.append(source["file_name"])
    
    # Build simplified log entry with only question, answer, and source file names
    log_entry: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "question": question,
        "answer": answer,
        "source_files": source_file_names,
    }
    
    try:
        # Log as JSON (one line per interaction)
        logger.info(json.dumps(log_entry, ensure_ascii=False))
    except Exception as e:
        # Fallback logging if JSON serialization fails
        logger.warning(f"Failed to serialize chat log: {e}")


def get_chat_log_stats() -> Dict[str, Any]:
    """Get statistics about chat logs"""
    try:
        log_files = list(CHAT_LOG_DIR.glob("chat_history.log*"))
        total_size = sum(f.stat().st_size for f in log_files if f.is_file())
        
        return {
            "log_directory": str(CHAT_LOG_DIR),
            "total_log_files": len(log_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
    except Exception as e:
        return {"error": str(e)}
