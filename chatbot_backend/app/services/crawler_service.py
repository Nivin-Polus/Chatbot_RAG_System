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
from app.core.vectorstore import VectorStore
from app.services.crawler import (
    CrawlConfig,
    CrawlStats,
    CrawlerEngine,
    ContentChunk
)

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
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.vector_store = VectorStore()
    
    def create_job(
        self,
        user_id: str,
        collection_id: str,
        target_url: str,
        max_pages: int = 100,
        max_depth: int = 5,
        use_sitemap: bool = True,
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
            "use_sitemap": use_sitemap
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
        
        logger.info(f"Created crawl job {job.job_id} for {target_url}")
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
        
        logger.info(f"Started crawl job {job_id}")
        return True
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running crawl job.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        if job_id in self._active_jobs:
            self._active_jobs[job_id].cancel()
            logger.info(f"Cancellation requested for job {job_id}")
        
        job = self.db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        if job and job.status == "running":
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
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
                logger.info(f"Deleted crawled content for job {job_id} from vector store")
            except Exception as e:
                logger.error(f"Failed to delete content from vector store: {e}")
        
        job = self.db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        if job:
            self.db.delete(job)
            self.db.commit()
            logger.info(f"Deleted job {job_id}")
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
                    job.update_from_stats(stats)
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")
    
    def _update_job_error(self, job_id: str, error: str):
        """Update job with error."""
        try:
            from app.core.database import SessionLocal
            with SessionLocal() as session:
                job = session.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
                if job:
                    job.status = "failed"
                    job.error_message = error
                    job.completed_at = datetime.utcnow()
                    session.commit()
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
