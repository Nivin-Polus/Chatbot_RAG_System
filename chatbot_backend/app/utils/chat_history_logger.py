"""Chat History Logger - Stores chat interactions in CSV files."""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, Optional

# Chat history log directory
CHAT_LOG_DIR = Path("storage/chat_logs")
CHAT_LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def _get_csv_file_path() -> Path:
    """Return the CSV file path for chat history."""
    return CHAT_LOG_DIR / "chat_history.csv"


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
    """Append a chat interaction to the CSV log file."""

    csv_path = _get_csv_file_path()
    write_header = not csv_path.exists()

    try:
        with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            if write_header:
                writer.writerow(["knowledge_base", "user", "question", "answer"])

            writer.writerow([
                collection_id or "",
                username or "",
                question or "",
                answer or "",
            ])
    except Exception as exc:
        logger.warning(f"Failed to write chat interaction to CSV: {exc}")


def get_chat_log_stats() -> Dict[str, Any]:
    """Get statistics about chat logs"""
    try:
        csv_path = _get_csv_file_path()
        total_size = csv_path.stat().st_size if csv_path.exists() else 0

        return {
            "log_directory": str(CHAT_LOG_DIR),
            "log_file": str(csv_path),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
    except Exception as e:
        return {"error": str(e)}
