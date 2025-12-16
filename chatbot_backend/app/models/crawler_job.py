# app/models/crawler_job.py
"""
Crawler Job Database Model
Tracks web crawling jobs and their status.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship

from app.models.base import Base


class CrawlerJob(Base):
    """Database model for crawler jobs."""
    
    __tablename__ = "crawler_jobs"
    
    # Primary key
    job_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # References
    collection_id = Column(String(36), ForeignKey("collections.collection_id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    
    # Target
    target_url = Column(String(2048), nullable=False)
    
    # Status
    status = Column(String(50), default="pending", nullable=False, index=True)
    # pending, running, completed, failed, cancelled, scheduled
    
    # Progress
    pages_discovered = Column(Integer, default=0)
    pages_crawled = Column(Integer, default=0)
    pages_skipped = Column(Integer, default=0)
    pages_failed = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    total_characters = Column(Integer, default=0)
    
    # Content tracking for comparison
    content_hash = Column(String(64), nullable=True)  # SHA256 of all content
    chunks_added = Column(Integer, default=0)  # New chunks in this run
    chunks_updated = Column(Integer, default=0)  # Updated chunks
    chunks_deleted = Column(Integer, default=0)  # Removed chunks
    
    # Current state
    current_url = Column(String(2048), nullable=True)
    
    # Configuration (stored as JSON)
    config = Column(JSON, nullable=True)
    
    # Scheduling
    is_scheduled = Column(Boolean, default=False, index=True)
    schedule_interval_hours = Column(Float, nullable=True)  # e.g., 48 for every 2 days
    next_run_at = Column(DateTime, nullable=True, index=True)
    last_successful_run = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)  # Total number of times this schedule has run
    
    # Errors
    error_message = Column(Text, nullable=True)
    consecutive_failures = Column(Integer, default=0)  # For disabling after too many failures
    
    # URL tracking (stored as JSON lists)
    crawled_urls = Column(JSON, nullable=True)  # List of {"url": str, "chunks": int, "title": str}
    failed_urls = Column(JSON, nullable=True)   # List of {"url": str, "reason": str}
    skipped_urls = Column(JSON, nullable=True)  # List of {"url": str, "reason": str}
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "job_id": self.job_id,
            "collection_id": self.collection_id,
            "user_id": self.user_id,
            "target_url": self.target_url,
            "status": self.status,
            "pages_discovered": self.pages_discovered,
            "pages_crawled": self.pages_crawled,
            "pages_skipped": self.pages_skipped,
            "pages_failed": self.pages_failed,
            "chunks_created": self.chunks_created,
            "chunks_added": self.chunks_added,
            "chunks_updated": self.chunks_updated,
            "chunks_deleted": self.chunks_deleted,
            "total_characters": self.total_characters,
            "current_url": self.current_url,
            "config": self.config,
            "is_scheduled": self.is_scheduled,
            "schedule_interval_hours": self.schedule_interval_hours,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_successful_run": self.last_successful_run.isoformat() if self.last_successful_run else None,
            "run_count": self.run_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress_percent": self._calculate_progress()
        }
    
    def _calculate_progress(self) -> int:
        """Calculate progress percentage."""
        if self.status == "completed":
            return 100
        if self.status == "pending" or self.status == "scheduled":
            return 0
        if self.pages_discovered == 0:
            return 5
        return min(95, int((self.pages_crawled / max(self.pages_discovered, 1)) * 100))
    
    def update_from_stats(self, stats):
        """Update from CrawlStats object."""
        self.status = stats.status
        self.pages_discovered = stats.pages_discovered
        self.pages_crawled = stats.pages_crawled
        self.pages_skipped = stats.pages_skipped
        self.pages_failed = stats.pages_failed
        self.chunks_created = stats.chunks_created
        self.total_characters = stats.total_characters
        self.current_url = stats.current_url
        self.error_message = stats.error_message
        
        # Save URL details when crawl is complete or failed
        if stats.status in ("completed", "failed", "cancelled"):
            self.crawled_urls = stats.crawled_urls if stats.crawled_urls else None
            self.failed_urls = stats.failed_urls if stats.failed_urls else None
            self.skipped_urls = stats.skipped_urls if stats.skipped_urls else None
        
        if stats.started_at and not self.started_at:
            self.started_at = stats.started_at
        if stats.completed_at:
            self.completed_at = stats.completed_at
