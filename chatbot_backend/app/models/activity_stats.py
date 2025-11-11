# app/models/activity_stats.py

from datetime import datetime
from typing import Dict

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func

from app.models.base import Base


class ActivityStats(Base):
    """Aggregate counters for activity tracking."""

    __tablename__ = "activity_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total_files_uploaded = Column(Integer, nullable=False, default=0)
    total_chat_sessions = Column(Integer, nullable=False, default=0)
    total_queries = Column(Integer, nullable=False, default=0)
    total_users = Column(Integer, nullable=False, default=0)
    recent_activity_24h = Column(Integer, nullable=False, default=0)

    last_document_upload = Column(DateTime(timezone=True), nullable=True)
    last_chat_session = Column(DateTime(timezone=True), nullable=True)
    last_activity = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_files_uploaded": self.total_files_uploaded,
            "total_chat_sessions": self.total_chat_sessions,
            "total_queries": self.total_queries,
            "total_users": self.total_users,
            "recent_activity_24h": self.recent_activity_24h,
            # Compatibility aliases for existing frontend labels
            "total_files": self.total_files_uploaded,
            "total_chats": self.total_chat_sessions,
            "recent_activity": self.recent_activity_24h,
            "last_document_upload": self.last_document_upload.isoformat() if self.last_document_upload else None,
            "last_chat_session": self.last_chat_session.isoformat() if self.last_chat_session else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }

    def touch_activity(self, timestamp: datetime) -> None:
        self.last_activity = timestamp
