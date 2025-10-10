# app/models/activity_log.py

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class ActivityLog(Base):
    """SQLAlchemy model for tracking high-level activities performed in the system."""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String(100), unique=True, nullable=False, index=True)
    activity_type = Column(String(50), nullable=False, index=True)

    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True, index=True)
    username = Column(String(150), nullable=False, index=True)

    details = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="activity_logs", lazy="joined", join_depth=1)

    def to_dict(self) -> Dict[str, Any]:
        timestamp = self.created_at
        if timestamp is not None and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return {
            "id": self.activity_id,
            "type": self.activity_type,
            "user": self.username,
            "timestamp": timestamp.astimezone(timezone.utc).isoformat() if timestamp else None,
            "details": self._safe_json_load(self.details) or {},
            "metadata": self._safe_json_load(self.metadata_json) or {},
        }

    @staticmethod
    def build_activity_id(activity_type: str) -> str:
        return f"{datetime.utcnow().timestamp()}_{activity_type}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _safe_json_dump(payload: Optional[Dict[str, Any]]) -> Optional[str]:
        if not payload:
            return None
        try:
            return json.dumps(payload, default=str)
        except Exception:
            return None

    @staticmethod
    def _safe_json_load(raw: Optional[str]) -> Optional[Dict[str, Any]]:
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            return {"value": data}
        except Exception:
            return None

    @classmethod
    def from_payload(
        cls,
        *,
        activity_id: str,
        activity_type: str,
        username: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> "ActivityLog":
        safe_timestamp = created_at
        if safe_timestamp is not None and safe_timestamp.tzinfo is None:
            safe_timestamp = safe_timestamp.replace(tzinfo=timezone.utc)

        return cls(
            activity_id=activity_id,
            activity_type=activity_type,
            username=username,
            user_id=user_id,
            details=cls._safe_json_dump(details),
            metadata_json=cls._safe_json_dump(metadata),
            created_at=safe_timestamp,
        )
