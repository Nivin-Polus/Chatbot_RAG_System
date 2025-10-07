# app/services/activity_tracker.py

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, DATABASE_AVAILABLE
from app.models.activity_log import ActivityLog
from app.models.activity_stats import ActivityStats
from app.models.user import User
from app.models.file_metadata import FileMetadata
from app.models.chat_tracking import ChatSession, ChatQuery

logger = logging.getLogger(__name__)


class ActivityTracker:
    def __init__(self, session_factory: Optional[Callable[[], Session]] = None):
        """Track system activities using the database."""
        self.session_factory = session_factory or SessionLocal

    def _get_session(self) -> Session:
        if not DATABASE_AVAILABLE or self.session_factory is None:
            raise RuntimeError("Database not available for activity tracking")
        session = self.session_factory()
        if session is None:
            raise RuntimeError("Failed to create database session for activity tracking")
        return session

    def _get_or_create_stats(self, session: Session, *, sync: bool = False) -> ActivityStats:
        stats = session.query(ActivityStats).first()
        if not stats:
            stats = ActivityStats()
            session.add(stats)
            # Always sync newly created stats to current state
            self._sync_with_existing_data(session, stats)
        elif sync:
            self._sync_with_existing_data(session, stats)
        return stats

    def _sync_with_existing_data(self, session: Session, stats: ActivityStats) -> None:
        """Ensure counters and timestamps reflect actual database state."""
        total_files = session.query(func.count(FileMetadata.file_id)).scalar() or 0
        stats.total_files_uploaded = total_files

        latest_file = session.query(func.max(FileMetadata.upload_timestamp)).scalar()
        if latest_file and (stats.last_document_upload is None or stats.last_document_upload < latest_file):
            stats.last_document_upload = latest_file

        total_sessions = session.query(func.count(ChatSession.session_id)).scalar() or 0
        stats.total_chat_sessions = total_sessions

        latest_session = session.query(func.max(ChatSession.created_at)).scalar()
        if latest_session and (stats.last_chat_session is None or stats.last_chat_session < latest_session):
            stats.last_chat_session = latest_session

        total_queries = session.query(func.count(ChatQuery.query_id)).scalar() or 0
        stats.total_queries = total_queries

        total_users = session.query(func.count(User.user_id)).scalar() or 0
        stats.total_users = total_users

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        recent_count = (
            session.query(func.count(ActivityLog.id))
            .filter(ActivityLog.created_at >= cutoff)
            .scalar()
            or 0
        )
        stats.recent_activity_24h = recent_count

        latest_activity = session.query(func.max(ActivityLog.created_at)).scalar()
        if latest_activity and (stats.last_activity is None or stats.last_activity < latest_activity):
            stats.last_activity = latest_activity

    def log_activity(self, activity_type: str, user: str, details: Dict = None, metadata: Dict = None):
        """Persist a new activity event."""
        timestamp = datetime.now(timezone.utc)
        session = self._get_session()
        try:
            user_obj = session.query(User).filter(User.username == user).first()
            activity_id = ActivityLog.build_activity_id(activity_type)

            activity = ActivityLog.from_payload(
                activity_id=activity_id,
                activity_type=activity_type,
                username=user,
                user_id=user_obj.user_id if user_obj else None,
                details=details,
                metadata=metadata,
                created_at=timestamp,
            )

            session.add(activity)

            stats = self._get_or_create_stats(session)

            if activity_type == "file_upload":
                stats.total_files_uploaded += 1
                stats.last_document_upload = timestamp
            elif activity_type == "chat_session_start":
                stats.total_chat_sessions += 1
                stats.last_chat_session = timestamp
            elif activity_type == "chat_query":
                stats.total_queries += 1
            elif activity_type in {"user_created", "user_registered"}:
                stats.total_users += 1

            stats.touch_activity(timestamp)

            session.commit()
            logger.info("Activity logged: %s by %s", activity_type, user)
        except Exception as exc:
            session.rollback()
            logger.error("Failed to log activity: %s", exc)
            raise
        finally:
            session.close()

    def get_recent_activities(self, limit: int = 50) -> List[Dict]:
        """Return the most recent activities."""
        session = self._get_session()
        try:
            records = (
                session.query(ActivityLog)
                    .order_by(desc(ActivityLog.created_at))
                    .limit(limit)
                    .all()
            )
            return [activity.to_dict() for activity in records]
        finally:
            session.close()

    def get_activities_by_type(self, activity_type: str, limit: int = 50) -> List[Dict]:
        session = self._get_session()
        try:
            records = (
                session.query(ActivityLog)
                    .filter(ActivityLog.activity_type == activity_type)
                    .order_by(desc(ActivityLog.created_at))
                    .limit(limit)
                    .all()
            )
            return [activity.to_dict() for activity in records]
        finally:
            session.close()

    def get_activities_by_user(self, user: str, limit: int = 50) -> List[Dict]:
        session = self._get_session()
        try:
            records = (
                session.query(ActivityLog)
                    .filter(ActivityLog.username == user)
                    .order_by(desc(ActivityLog.created_at))
                    .limit(limit)
                    .all()
            )
            return [activity.to_dict() for activity in records]
        finally:
            session.close()

    def get_stats(self) -> Dict:
        session = self._get_session()
        try:
            stats = self._get_or_create_stats(session, sync=True)
            session.commit()
            return stats.to_dict()
        finally:
            session.close()

    def get_activity_summary(self) -> Dict:
        session = self._get_session()
        try:
            stats = self._get_or_create_stats(session, sync=True)

            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=24)

            recent = (
                session.query(ActivityLog.activity_type, func.count(ActivityLog.id))
                    .filter(ActivityLog.created_at >= cutoff)
                    .group_by(ActivityLog.activity_type)
                    .all()
            )
            recent_counts = {activity_type: count for activity_type, count in recent}

            total_activities = session.query(func.count(ActivityLog.id)).scalar() or 0

            session.commit()

            return {
                "stats": stats.to_dict(),
                "recent_24h": recent_counts,
                "total_activities": total_activities,
            }
        finally:
            session.close()

    def clear_activities(self, days_to_keep: int = 30):
        session = self._get_session()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            deleted = (
                session.query(ActivityLog)
                    .filter(ActivityLog.created_at < cutoff)
                    .delete()
            )
            session.commit()
            logger.info("Cleared %d activities older than %d days", deleted, days_to_keep)
        finally:
            session.close()


# Global activity tracker instance
activity_tracker = ActivityTracker()
