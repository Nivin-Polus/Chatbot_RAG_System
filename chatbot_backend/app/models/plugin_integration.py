from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class PluginIntegration(Base):
    """Mapping between external plugin website links and collections."""

    __tablename__ = "plugin_integrations"
    __table_args__ = (
        UniqueConstraint("normalized_url", name="uq_plugin_integrations_normalized_url"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    collection_id = Column(String(50), ForeignKey("collections.collection_id"), nullable=False, index=True)
    website_url = Column(String(500), nullable=False)
    normalized_url = Column(String(500), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)

    collection = relationship("Collection", back_populates="plugin_integrations")
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<PluginIntegration(collection='{self.collection_id}', normalized_url='{self.normalized_url}')>"
