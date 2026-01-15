# app/services/crawler_service.py
"""
Crawler Service
High-level service for managing crawl jobs and integrating with vector store.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Callable
from datetime import datetime
import threading

from sqlalchemy.orm import Session

from app.models.crawler_job import CrawlerJob
from app.models.user import User
from app.core.vectorstore import VectorStore
from app.services.crawler import (
    CrawlConfig,
    CrawlStats,
    CrawlerEngine,
    ContentChunk
)
from app.services.activity_tracker import activity_tracker

logger = logging.getLogger("crawler_service")


class CrawlerService:
    """
    Service for managing web crawl jobs.
    
    Handles:
    - Job creation and tracking
    - Background crawl execution
    - Vector store integration
    - Progress updates
    """
    
    # In-memory job tracking for active crawls
    _active_jobs: Dict[str, CrawlerEngine] = {}
    _job_threads: Dict[str, threading.Thread] = {}
    
    # Global crawl limit - only 1 crawl allowed at a time
    MAX_CONCURRENT_CRAWLS = 1
    _queue_lock = threading.Lock()
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.vector_store = VectorStore()
    
    @classmethod
    def get_active_crawl_count(cls) -> int:
        """Get the number of currently running crawls."""
        return len(cls._active_jobs)
    
    @classmethod
    def is_crawl_available(cls) -> bool:
        """Check if a new crawl can start immediately."""
        return cls.get_active_crawl_count() < cls.MAX_CONCURRENT_CRAWLS
    
    @classmethod
    def get_crawl_status(cls) -> dict:
        """Get global crawl status including active jobs."""
        with cls._queue_lock:
            active_job_ids = list(cls._active_jobs.keys())
            return {
                "is_crawl_running": len(active_job_ids) > 0,
                "active_crawl_count": len(active_job_ids),
                "active_job_ids": active_job_ids,
                "max_concurrent": cls.MAX_CONCURRENT_CRAWLS,
                "can_start_new": len(active_job_ids) < cls.MAX_CONCURRENT_CRAWLS
            }
    
    def create_job(
        self,
        user_id: str,
        collection_id: str,
        target_url: str,
        max_pages: int = 100,
        max_depth: int = 5,
        use_sitemap: bool = True,
        process_documents: bool = True,
        exclude_patterns: Optional[List[str]] = None,
        include_keywords: Optional[List[str]] = None
    ) -> CrawlerJob:
        """
        Create a new crawl job.
        
        Args:
            user_id: User initiating the crawl
            collection_id: Target collection for chunks
            target_url: URL to start crawling
            max_pages: Maximum pages to crawl
            max_depth: Maximum link depth
            use_sitemap: Whether to use sitemap for discovery
            process_documents: Whether to download and process PDF/Word documents
            exclude_patterns: URL patterns to exclude
            include_keywords: Only crawl URLs containing these keywords
            
        Returns:
            CrawlerJob instance
        """
        # Build config
        config_dict = {
            "target_url": target_url,
            "collection_id": collection_id,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "use_sitemap": use_sitemap,
            "process_documents": process_documents
        }
        
        if exclude_patterns:
            config_dict["exclude_patterns"] = exclude_patterns
        if include_keywords:
            config_dict["include_keywords"] = include_keywords
        
        # Create job record
        job = CrawlerJob(
            user_id=user_id,
            collection_id=collection_id,
            target_url=target_url,
            status="pending",
            config=config_dict
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        logger.debug(f"Created crawl job {job.job_id} for {target_url}")
        return job
    
    def start_job(self, job_id: str) -> bool:
        """
        Start a crawl job in the background.
        
        Args:
            job_id: Job ID to start
            
        Returns:
            True if started successfully
        """
        job = self.db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        
        if not job:
            logger.error(f"Job not found: {job_id}")
            return False
        
        if job.status != "pending":
            logger.warning(f"Job {job_id} is not pending (status: {job.status})")
            return False
        
        # Create config from stored settings
        config = CrawlConfig(**job.config)
        
        # Create progress callback that updates the database
        def on_progress(stats: CrawlStats):
            self._update_job_progress(job_id, stats)
        
        # Create chunk callback for immediate vector storage
        def on_chunk(chunk: ContentChunk):
            self._store_chunk(chunk)
        
        # Create engine
        engine = CrawlerEngine(
            config=config,
            on_progress=on_progress,
            on_chunk=on_chunk
        )
        
        # Store reference for cancellation
        self._active_jobs[job_id] = engine
        
        # Start in background thread
        def run_crawl():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(engine.crawl(job_id))
            except Exception as e:
                logger.error(f"Crawl failed: {e}")
                self._update_job_error(job_id, str(e))
            finally:
                # Cleanup
                if job_id in self._active_jobs:
                    del self._active_jobs[job_id]
                if job_id in self._job_threads:
                    del self._job_threads[job_id]
        
        thread = threading.Thread(target=run_crawl, daemon=True)
        self._job_threads[job_id] = thread
        thread.start()
        
        # Update status
        job.status = "running"
        job.started_at = datetime.utcnow()
        self.db.commit()
        
        logger.debug(f"Started crawl job {job_id}")
        return True
    
    def cancel_job(self, job_id: str, delete_data: bool = False) -> bool:
        """
        Cancel a running crawl job.
        
        Args:
            job_id: Job ID to cancel
            delete_data: If True, delete all crawled data from the vector store
            
        Returns:
            True if cancelled successfully
        """
        if job_id in self._active_jobs:
            self._active_jobs[job_id].cancel()
            logger.debug(f"Cancellation requested for job {job_id}")
        
        job = self.db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        if job and job.status == "running":
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
            
            # Delete crawled data if requested
            if delete_data and job.collection_id:
                try:
                    vector_store = VectorStore()
                    # Delete all chunks from this crawl job
                    deleted_count = vector_store.delete_by_filter({
                        "crawl_job_id": job_id,
                        "collection_id": job.collection_id
                    })
                    logger.info(f"Deleted {deleted_count} chunks from cancelled job {job_id}")
                    
                    # Reset chunk counters since data was deleted
                    job.chunks_created = 0
                    job.chunks_added = 0
                except Exception as e:
                    logger.error(f"Failed to delete chunks for job {job_id}: {e}")
                    # Continue with cancellation even if deletion fails
            
            self.db.commit()
            return True
        
        return False
    
    def get_job(self, job_id: str) -> Optional[CrawlerJob]:
        """Get a job by ID."""
        return self.db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
    
    def get_jobs_for_user(self, user_id: str, limit: int = 50) -> List[CrawlerJob]:
        """Get jobs for a user."""
        return self.db.query(CrawlerJob).filter(
            CrawlerJob.user_id == user_id
        ).order_by(CrawlerJob.created_at.desc()).limit(limit).all()
    
    def get_jobs_for_collection(self, collection_id: str, limit: int = 50) -> List[CrawlerJob]:
        """Get jobs for a collection."""
        return self.db.query(CrawlerJob).filter(
            CrawlerJob.collection_id == collection_id
        ).order_by(CrawlerJob.created_at.desc()).limit(limit).all()
    
    def delete_job(self, job_id: str, delete_content: bool = True) -> bool:
        """
        Delete a job and optionally its chunks from vector store.
        
        Args:
            job_id: Job ID to delete
            delete_content: If True, also delete crawled content from vector store
            
        Returns:
            True if deleted
        """
        # Cancel if running
        self.cancel_job(job_id)
        
        # Delete content from vector store first
        if delete_content:
            try:
                self.vector_store.delete_documents_by_crawl_job_id(job_id)
                logger.debug(f"Deleted crawled content for job {job_id} from vector store")
            except Exception as e:
                logger.error(f"Failed to delete content from vector store: {e}")
        
        job = self.db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        if job:
            self.db.delete(job)
            self.db.commit()
            logger.debug(f"Deleted job {job_id}")
            return True
        
        return False
    
    def _update_job_progress(self, job_id: str, stats: CrawlStats):
        """Update job progress in database."""
        try:
            # Use a new session for thread safety
            from app.core.database import SessionLocal
            with SessionLocal() as session:
                job = session.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
                if job:
                    # Track previous status to detect completion/failure
                    previous_status = job.status
                    job.update_from_stats(stats)
                    session.commit()
                    
                    # Log activity when crawl completes or fails
                    if stats.status in ("completed", "failed") and previous_status != stats.status:
                        try:
                            user = session.query(User).filter(User.user_id == job.user_id).first()
                            username = user.username if user else "unknown"
                            
                            activity_type = "crawl_completed" if stats.status == "completed" else "crawl_failed"
                            activity_tracker.log_activity(
                                activity_type=activity_type,
                                user=username,
                                details={
                                    "job_id": job_id,
                                    "target_url": job.target_url,
                                    "collection_id": job.collection_id,
                                    "pages_crawled": stats.pages_crawled,
                                    "pages_failed": stats.pages_failed,
                                    "chunks_created": stats.chunks_created,
                                    "error_message": stats.error_message if stats.status == "failed" else None,
                                },
                            )
                        except Exception as log_error:
                            logger.error(f"Failed to log crawl completion activity: {log_error}")
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")
    
    def _update_job_error(self, job_id: str, error: str):
        """Update job with error."""
        try:
            from app.core.database import SessionLocal
            with SessionLocal() as session:
                job = session.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
                if job:
                    previous_status = job.status
                    job.status = "failed"
                    job.error_message = error
                    job.completed_at = datetime.utcnow()
                    session.commit()
                    
                    # Log activity when crawl fails
                    if previous_status != "failed":
                        try:
                            user = session.query(User).filter(User.user_id == job.user_id).first()
                            username = user.username if user else "unknown"
                            
                            activity_tracker.log_activity(
                                activity_type="crawl_failed",
                                user=username,
                                details={
                                    "job_id": job_id,
                                    "target_url": job.target_url,
                                    "collection_id": job.collection_id,
                                    "error_message": error,
                                },
                            )
                        except Exception as log_error:
                            logger.error(f"Failed to log crawl failure activity: {log_error}")
        except Exception as e:
            logger.error(f"Failed to update job error: {e}")
    
    def _store_chunk(self, chunk: ContentChunk):
        """Store a chunk in the vector database."""
        try:
            self.vector_store.add_document(
                doc_text=chunk.text,
                metadata=chunk.to_vector_metadata()
            )
        except Exception as e:
            logger.error(f"Failed to store chunk: {e}")
    
    @classmethod
    def is_job_active(cls, job_id: str) -> bool:
        """Check if a job is currently running."""
        return job_id in cls._active_jobs
    
    @classmethod
    def is_job_stale(cls, job_id: str, stale_seconds: int = 300) -> bool:
        """
        Check if a running job appears stuck (no progress in N seconds).
        
        Args:
            job_id: Job ID to check
            stale_seconds: Seconds without activity to consider stale (default: 5 min)
            
        Returns:
            True if the job is stale (no recent activity), False otherwise
        """
        if job_id not in cls._active_jobs:
            return False
        
        engine = cls._active_jobs[job_id]
        last_activity = engine.get_last_activity()
        
        if last_activity is None:
            # Job started but hasn't processed any pages yet
            return False
        
        elapsed = (datetime.utcnow() - last_activity).total_seconds()
        return elapsed > stale_seconds
    
    @classmethod
    def get_job_health(cls, job_id: str) -> dict:
        """
        Get detailed health status of an active job.
        
        Returns:
            Dictionary with health information including:
            - is_active: Whether the job is currently running
            - is_stale: Whether the job appears stuck
            - last_activity_seconds_ago: Time since last successful activity
            - circuit_breaker_open: Whether backoff circuit is open
            - consecutive_failures: Number of consecutive failures
        """
        if job_id not in cls._active_jobs:
            return {
                "is_active": False,
                "is_stale": False,
                "last_activity_seconds_ago": None,
                "circuit_breaker_open": False,
                "consecutive_failures": 0
            }
        
        engine = cls._active_jobs[job_id]
        last_activity = engine.get_last_activity()
        
        last_activity_secs = None
        if last_activity:
            last_activity_secs = (datetime.utcnow() - last_activity).total_seconds()
        
        stale_threshold = getattr(engine.config, 'stale_heartbeat_seconds', 300)
        
        return {
            "is_active": True,
            "is_stale": last_activity_secs is not None and last_activity_secs > stale_threshold,
            "last_activity_seconds_ago": round(last_activity_secs, 1) if last_activity_secs else None,
            "circuit_breaker_open": engine._circuit_open,
            "consecutive_failures": engine._total_consecutive_failures
        }
