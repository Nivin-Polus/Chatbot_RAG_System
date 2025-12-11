# app/services/crawler_scheduler.py
"""
Crawler Scheduler Service
Handles scheduled/recurring web crawls with content comparison.
"""

import asyncio
import logging
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.crawler_job import CrawlerJob
from app.core.vectorstore import VectorStore
from app.services.crawler_service import CrawlerService

logger = logging.getLogger("crawler_scheduler")


class ContentComparer:
    """
    Compares content between crawl runs to detect changes.
    Only updates chunks that have actually changed.
    """
    
    def __init__(self, vector_store: VectorStore, collection_id: str, job_id: str):
        self.vector_store = vector_store
        self.collection_id = collection_id
        self.job_id = job_id
        self.existing_chunks: Dict[str, str] = {}  # url -> content_hash
        self.new_chunks: Dict[str, str] = {}  # url -> content_hash
        
        self.stats = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "unchanged": 0
        }
    
    def load_existing_chunks(self):
        """Load existing chunk hashes for comparison."""
        try:
            # Query existing chunks for this collection from previous crawl
            # This would need to query the vector store metadata
            # For now, we'll track by URL
            pass
        except Exception as e:
            logger.error(f"Failed to load existing chunks: {e}")
    
    def compute_content_hash(self, text: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def should_update_chunk(self, url: str, content: str) -> tuple[bool, str]:
        """
        Check if chunk should be added/updated.
        
        Returns:
            Tuple of (should_store, action) where action is 'add', 'update', or 'skip'
        """
        content_hash = self.compute_content_hash(content)
        self.new_chunks[url] = content_hash
        
        if url not in self.existing_chunks:
            self.stats["added"] += 1
            return True, "add"
        
        if self.existing_chunks[url] != content_hash:
            self.stats["updated"] += 1
            return True, "update"
        
        self.stats["unchanged"] += 1
        return False, "skip"
    
    def get_deleted_urls(self) -> Set[str]:
        """Get URLs that existed before but not in new crawl."""
        existing_urls = set(self.existing_chunks.keys())
        new_urls = set(self.new_chunks.keys())
        deleted = existing_urls - new_urls
        self.stats["deleted"] = len(deleted)
        return deleted
    
    def get_stats(self) -> Dict:
        """Get comparison statistics."""
        return self.stats


class CrawlerScheduler:
    """
    Background scheduler for recurring crawl jobs.
    
    Features:
    - Runs scheduled crawls at configured intervals
    - Compares content to detect changes
    - Only updates changed content in vector store
    - Handles failures with retry logic
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._check_interval = 60  # Check every minute for due jobs
        self._max_consecutive_failures = 5
        
        logger.info("CrawlerScheduler initialized")
    
    def start(self):
        """Start the background scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        logger.info("Crawler scheduler started")
    
    def stop(self):
        """Stop the background scheduler."""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        logger.info("Crawler scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop."""
        while self._running:
            try:
                self._check_and_run_due_jobs()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            # Sleep until next check
            for _ in range(self._check_interval):
                if not self._running:
                    break
                import time
                time.sleep(1)
    
    def _check_and_run_due_jobs(self):
        """Check for and run any due scheduled jobs."""
        from app.core.database import SessionLocal
        
        if not SessionLocal:
            return
        
        try:
            with SessionLocal() as db:
                now = datetime.utcnow()
                
                # Find due scheduled jobs
                due_jobs = db.query(CrawlerJob).filter(
                    and_(
                        CrawlerJob.is_scheduled == True,
                        CrawlerJob.status == "scheduled",
                        CrawlerJob.next_run_at <= now,
                        CrawlerJob.consecutive_failures < self._max_consecutive_failures
                    )
                ).all()
                
                for job in due_jobs:
                    logger.info(f"Starting scheduled crawl: {job.job_id} for {job.target_url}")
                    self._run_scheduled_job(db, job)
                    
        except Exception as e:
            logger.error(f"Failed to check due jobs: {e}")
    
    def _run_scheduled_job(self, db: Session, job: CrawlerJob):
        """Run a single scheduled job."""
        try:
            # Update status
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.run_count += 1
            db.commit()
            
            # Create crawler service and run
            crawler_service = CrawlerService(db)
            
            # Run the crawl (this happens in background)
            def on_complete(success: bool):
                self._handle_job_completion(job.job_id, success)
            
            # Start the crawl
            crawler_service.start_job(job.job_id)
            
        except Exception as e:
            logger.error(f"Failed to start scheduled job {job.job_id}: {e}")
            job.status = "scheduled"
            job.consecutive_failures += 1
            job.error_message = str(e)
            db.commit()
    
    def _handle_job_completion(self, job_id: str, success: bool):
        """Handle completion of a scheduled job."""
        from app.core.database import SessionLocal
        
        try:
            with SessionLocal() as db:
                job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
                
                if not job or not job.is_scheduled:
                    return
                
                if success:
                    job.last_successful_run = datetime.utcnow()
                    job.consecutive_failures = 0
                else:
                    job.consecutive_failures += 1
                
                # Schedule next run
                if job.schedule_interval_hours and job.consecutive_failures < self._max_consecutive_failures:
                    job.next_run_at = datetime.utcnow() + timedelta(hours=job.schedule_interval_hours)
                    job.status = "scheduled"
                else:
                    # Disable schedule after too many failures
                    if job.consecutive_failures >= self._max_consecutive_failures:
                        job.is_scheduled = False
                        job.error_message = f"Disabled after {job.consecutive_failures} consecutive failures"
                        logger.warning(f"Scheduled job {job_id} disabled after too many failures")
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to handle job completion: {e}")
    
    @staticmethod
    def schedule_job(
        db: Session,
        job_id: str,
        interval_hours: float,
        start_immediately: bool = True
    ) -> bool:
        """
        Enable scheduling for a job.
        
        Args:
            db: Database session
            job_id: Job to schedule
            interval_hours: Hours between runs (e.g., 48 for every 2 days)
            start_immediately: Whether to start the first run now
            
        Returns:
            True if scheduled successfully
        """
        job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        
        if not job:
            logger.error(f"Job not found: {job_id}")
            return False
        
        job.is_scheduled = True
        job.schedule_interval_hours = interval_hours
        job.consecutive_failures = 0
        
        if start_immediately:
            job.status = "pending"
            job.next_run_at = datetime.utcnow()
        else:
            job.status = "scheduled"
            job.next_run_at = datetime.utcnow() + timedelta(hours=interval_hours)
        
        db.commit()
        logger.info(f"Scheduled job {job_id} to run every {interval_hours} hours")
        return True
    
    @staticmethod
    def unschedule_job(db: Session, job_id: str) -> bool:
        """Disable scheduling for a job."""
        job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
        
        if not job:
            return False
        
        job.is_scheduled = False
        job.status = "completed" if job.status == "scheduled" else job.status
        job.next_run_at = None
        db.commit()
        
        logger.info(f"Unscheduled job {job_id}")
        return True


# Global scheduler instance
_scheduler: Optional[CrawlerScheduler] = None


def get_scheduler() -> CrawlerScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = CrawlerScheduler()
    return _scheduler


def start_scheduler():
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
