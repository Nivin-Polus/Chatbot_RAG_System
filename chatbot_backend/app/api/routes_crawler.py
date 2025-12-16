# app/api/routes_crawler.py
"""
Web Crawler API Routes
Endpoints for managing web crawl jobs.
"""

import re
import logging
from datetime import datetime
from typing import Optional, List
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.crawler_job import CrawlerJob
from app.models.collection import Collection
from app.services.crawler_service import CrawlerService
from app.services.activity_tracker import activity_tracker

logger = logging.getLogger("crawler_routes")
router = APIRouter()


# ================================
# Request/Response Models
# ================================

class StartCrawlRequest(BaseModel):
    """Request to start a new crawl job."""
    
    target_url: str = Field(..., description="URL to start crawling")
    collection_id: str = Field(..., description="Target knowledge base collection")
    
    # Optional settings
    max_pages: int = Field(default=0, ge=0, le=100000, description="Maximum pages to crawl (0 = unlimited)")
    max_depth: int = Field(default=5, ge=1, le=15, description="Maximum link depth")
    use_sitemap: bool = Field(default=True, description="Use sitemap for URL discovery")
    process_documents: bool = Field(default=True, description="Download and process PDF/Word documents")
    
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="URL patterns to exclude (e.g., '/login', '/admin')"
    )
    include_keywords: Optional[List[str]] = Field(
        default=None,
        description="Only crawl URLs containing these keywords"
    )
    
    @validator('target_url')
    def validate_url(cls, v):
        """Validate that target_url is a proper URL."""
        if not v:
            raise ValueError("URL is required")
        
        # Add protocol if missing
        if not v.startswith(('http://', 'https://')):
            v = 'https://' + v
        
        # Parse and validate
        parsed = urlparse(v)
        if not parsed.netloc:
            raise ValueError("Invalid URL format")
        
        # Check for valid domain
        if not re.match(r'^[\w\-\.]+\.\w+', parsed.netloc):
            raise ValueError("Invalid domain")
        
        return v


class CrawlJobResponse(BaseModel):
    """Response model for a crawl job."""
    
    job_id: str
    collection_id: str
    target_url: str
    status: str
    pages_discovered: int
    pages_crawled: int
    pages_skipped: int
    pages_failed: int
    chunks_created: int
    chunks_added: Optional[int] = 0
    chunks_updated: Optional[int] = 0
    chunks_deleted: Optional[int] = 0
    total_characters: int
    progress_percent: int
    current_url: Optional[str] = None
    error_message: Optional[str] = None
    is_scheduled: Optional[bool] = False
    schedule_interval_hours: Optional[float] = None
    next_run_at: Optional[str] = None
    last_successful_run: Optional[str] = None
    run_count: Optional[int] = 0
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class ScheduleCrawlRequest(BaseModel):
    """Request to schedule recurring crawls."""
    
    interval_hours: float = Field(
        default=48.0,
        ge=1.0,
        le=8760.0,  # Max 1 year (365 days)
        description="Hours between crawls (e.g., 48 for every 2 days, 1440 for 2 months, 4320 for 6 months, 8760 for 1 year)"
    )
    start_immediately: bool = Field(
        default=True,
        description="Whether to start the first crawl immediately"
    )


class CrawlJobListResponse(BaseModel):
    """Response for listing crawl jobs."""
    
    jobs: List[CrawlJobResponse]
    total: int


# ================================
# API Endpoints
# ================================

@router.post("/start", response_model=CrawlJobResponse)
async def start_crawl(
    request: StartCrawlRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new web crawl job.
    
    Crawls the target URL and its internal links, extracting content
    and storing it in the specified knowledge base collection.
    
    - **target_url**: The starting URL for the crawl
    - **collection_id**: Target knowledge base to store extracted content
    - **max_pages**: Maximum number of pages to crawl (1-10000)
    - **max_depth**: Maximum link depth to follow (1-10)
    - **use_sitemap**: Whether to use sitemap.xml for URL discovery
    - **exclude_patterns**: List of URL patterns to exclude
    - **include_keywords**: Only include URLs containing these keywords
    """
    # Verify user has access to collection
    # TODO: Add collection access check based on user role
    
    # Check if user is admin or superadmin
    if current_user.role not in ['super_admin', 'superadmin', 'admin', 'user_admin', 'useradmin']:
        raise HTTPException(
            status_code=403,
            detail="Only admins can create crawl jobs"
        )
    
    # Create crawler service
    crawler_service = CrawlerService(db)
    
    try:
        # Create job
        job = crawler_service.create_job(
            user_id=current_user.user_id,
            collection_id=request.collection_id,
            target_url=request.target_url,
            max_pages=request.max_pages,
            max_depth=request.max_depth,
            use_sitemap=request.use_sitemap,
            process_documents=request.process_documents,
            exclude_patterns=request.exclude_patterns,
            include_keywords=request.include_keywords
        )
        
        # Start job in background
        background_tasks.add_task(crawler_service.start_job, job.job_id)
        
        logger.info(f"User {current_user.username} started crawl job {job.job_id}")
        
        # Log activity
        activity_tracker.log_activity(
            activity_type="crawl_started",
            user=current_user.username,
            details={
                "job_id": job.job_id,
                "target_url": request.target_url,
                "collection_id": request.collection_id,
                "max_pages": request.max_pages,
                "max_depth": request.max_depth,
            },
        )
        
        return CrawlJobResponse(**job.to_dict())
        
    except Exception as e:
        logger.error(f"Failed to start crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=CrawlJobListResponse)
async def list_crawl_jobs(
    collection_id: Optional[str] = Query(None, description="Filter by collection"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List crawl jobs.
    
    Returns jobs for the current user, optionally filtered by collection or status.
    Superadmins can see all jobs.
    """
    query = db.query(CrawlerJob)
    
    # Filter by user unless superadmin, or user_admin viewing their own collection
    if current_user.role not in ['super_admin', 'superadmin']:
        # Check if user is admin of the requested collection
        is_collection_admin = False
        if collection_id and current_user.role in ['user_admin', 'useradmin', 'admin']:
            collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
            if collection and collection.admin_user_id == current_user.user_id:
                is_collection_admin = True
        
        # If not collection admin, restrict to own jobs
        if not is_collection_admin:
            query = query.filter(CrawlerJob.user_id == current_user.user_id)
    
    # Apply filters
    if collection_id:
        query = query.filter(CrawlerJob.collection_id == collection_id)
    
    if status:
        query = query.filter(CrawlerJob.status == status)
    
    # Get total count (before ordering to avoid sort memory issues)
    total = query.count()
    
    # Get jobs with error handling for MySQL sort buffer issues
    try:
        # Try the optimized query: use a subquery to get IDs first, then fetch full records
        # This reduces the amount of data MySQL needs to sort
        from sqlalchemy import select
        
        # Build the same filters for the subquery
        subquery_filters = []
        if current_user.role not in ['super_admin', 'superadmin']:
            is_collection_admin = False
            if collection_id and current_user.role in ['user_admin', 'useradmin', 'admin']:
                collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
                if collection and collection.admin_user_id == current_user.user_id:
                    is_collection_admin = True
            if not is_collection_admin:
                subquery_filters.append(CrawlerJob.user_id == current_user.user_id)
        
        if collection_id:
            subquery_filters.append(CrawlerJob.collection_id == collection_id)
        if status:
            subquery_filters.append(CrawlerJob.status == status)
        
        # Create subquery to get job_ids ordered by created_at
        subquery = select(CrawlerJob.job_id)
        for filter_condition in subquery_filters:
            subquery = subquery.where(filter_condition)
        subquery = subquery.order_by(CrawlerJob.created_at.desc()).limit(limit)
        
        # Execute subquery to get IDs
        result = db.execute(subquery)
        job_ids = [row[0] for row in result.fetchall()]
        
        if job_ids:
            # Fetch full records - use a dictionary to preserve order
            jobs_dict = {job.job_id: job for job in db.query(CrawlerJob).filter(CrawlerJob.job_id.in_(job_ids)).all()}
            # Reorder based on job_ids list
            jobs = [jobs_dict[jid] for jid in job_ids if jid in jobs_dict]
        else:
            jobs = []
            
    except Exception as e:
        # Fallback: try original query with error handling
        logger.warning(f"Optimized query failed, trying fallback: {e}")
        try:
            jobs = query.order_by(CrawlerJob.created_at.desc()).limit(limit).all()
        except Exception as fallback_error:
            error_str = str(fallback_error).lower()
            logger.error(f"Failed to fetch crawl jobs: {fallback_error}")
            
            # Check if it's the sort memory error
            if "sort memory" in error_str or "1038" in error_str or "out of sort memory" in error_str:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Database query failed due to large dataset. "
                        "Please contact administrator to: "
                        "1) Add an index on crawler_jobs.created_at column, or "
                        "2) Increase MySQL sort_buffer_size configuration. "
                        "Error: " + str(fallback_error)
                    )
                )
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to fetch crawl jobs: {str(fallback_error)}"
            )
    
    return CrawlJobListResponse(
        jobs=[CrawlJobResponse(**job.to_dict()) for job in jobs],
        total=total
    )


@router.get("/jobs/{job_id}", response_model=CrawlJobResponse)
async def get_crawl_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get status of a specific crawl job.
    
    Returns current progress, statistics, and status of the crawl.
    """
    job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check access
    if current_user.role not in ['super_admin', 'superadmin']:
        if job.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return CrawlJobResponse(**job.to_dict())


@router.get("/jobs/{job_id}/urls")
async def get_crawl_job_urls(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed URL breakdown for a crawl job.
    
    Returns lists of crawled, failed, and skipped URLs with reasons.
    Only available after the crawl has completed.
    """
    job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check access
    if current_user.role not in ['super_admin', 'superadmin']:
        if job.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "job_id": job.job_id,
        "target_url": job.target_url,
        "status": job.status,
        "summary": {
            "total_crawled": len(job.crawled_urls or []),
            "total_failed": len(job.failed_urls or []),
            "total_skipped": len(job.skipped_urls or [])
        },
        "crawled_urls": job.crawled_urls or [],
        "failed_urls": job.failed_urls or [],
        "skipped_urls": job.skipped_urls or []
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_crawl_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a running crawl job.
    
    Stops the crawl but preserves any content already extracted.
    """
    job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check access
    if current_user.role not in ['super_admin', 'superadmin']:
        if job.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    if job.status != "running":
        raise HTTPException(status_code=400, detail="Job is not running")
    
    # Cancel
    crawler_service = CrawlerService(db)
    success = crawler_service.cancel_job(job_id)
    
    if success:
        logger.info(f"User {current_user.username} cancelled job {job_id}")
        
        # Log activity
        activity_tracker.log_activity(
            activity_type="crawl_cancelled",
            user=current_user.username,
            details={
                "job_id": job_id,
                "target_url": job.target_url,
                "collection_id": job.collection_id,
            },
        )
        
        return {"status": "cancelled", "job_id": job_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@router.delete("/jobs/{job_id}")
async def delete_crawl_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a crawl job.
    
    Removes the job record. Running jobs will be cancelled first.
    Note: Extracted content in the vector store is not removed.
    """
    job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check access
    if current_user.role not in ['super_admin', 'superadmin']:
        if job.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete
    crawler_service = CrawlerService(db)
    success = crawler_service.delete_job(job_id)
    
    if success:
        logger.info(f"User {current_user.username} deleted job {job_id}")
        
        # Log activity
        activity_tracker.log_activity(
            activity_type="crawl_deleted",
            user=current_user.username,
            details={
                "job_id": job_id,
                "target_url": job.target_url,
                "collection_id": job.collection_id,
            },
        )
        
        return {"status": "deleted", "job_id": job_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete job")


@router.post("/jobs/{job_id}/recrawl", response_model=CrawlJobResponse)
async def recrawl(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Re-run a completed crawl job.
    
    Creates a new crawl job with the same settings as the original.
    Useful for refreshing content from a previously crawled site.
    """
    original_job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
    
    if not original_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check access
    if current_user.role not in ['super_admin', 'superadmin']:
        if original_job.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Create new job with same config
    crawler_service = CrawlerService(db)
    
    config = original_job.config or {}
    
    new_job = crawler_service.create_job(
        user_id=current_user.user_id,
        collection_id=original_job.collection_id,
        target_url=original_job.target_url,
        max_pages=config.get('max_pages', 0),  # 0 = unlimited
        max_depth=config.get('max_depth', 5),
        use_sitemap=config.get('use_sitemap', True),
        process_documents=config.get('process_documents', True),
        exclude_patterns=config.get('exclude_patterns'),
        include_keywords=config.get('include_keywords')
    )
    
    # Start in background
    background_tasks.add_task(crawler_service.start_job, new_job.job_id)
    
    logger.info(f"User {current_user.username} started recrawl {new_job.job_id} (from {job_id})")
    
    # Log activity
    activity_tracker.log_activity(
        activity_type="crawl_recrawled",
        user=current_user.username,
        details={
            "new_job_id": new_job.job_id,
            "original_job_id": job_id,
            "target_url": original_job.target_url,
            "collection_id": original_job.collection_id,
        },
    )
    
    return CrawlJobResponse(**new_job.to_dict())


@router.post("/jobs/{job_id}/schedule", response_model=CrawlJobResponse)
async def schedule_crawl(
    job_id: str,
    request: ScheduleCrawlRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable scheduled recurring crawls for a job.
    
    The crawler will automatically re-run at the specified interval,
    comparing content and only updating changed pages.
    
    - **interval_hours**: Hours between runs (e.g., 48 for every 2 days)
    - **start_immediately**: Whether to run the first crawl now
    """
    job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check access
    if current_user.role not in ['super_admin', 'superadmin']:
        if job.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Schedule the job
    from app.services.crawler_scheduler import CrawlerScheduler
    
    success = CrawlerScheduler.schedule_job(
        db=db,
        job_id=job_id,
        interval_hours=request.interval_hours,
        start_immediately=request.start_immediately
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to schedule job")
    
    # Refresh job from DB
    db.refresh(job)
    
    # If starting immediately, kick off the crawl
    if request.start_immediately:
        crawler_service = CrawlerService(db)
        background_tasks.add_task(crawler_service.start_job, job_id)
    
    logger.info(f"User {current_user.username} scheduled job {job_id} every {request.interval_hours} hours")
    
    # Log activity
    activity_tracker.log_activity(
        activity_type="crawl_scheduled",
        user=current_user.username,
        details={
            "job_id": job_id,
            "target_url": job.target_url,
            "collection_id": job.collection_id,
            "interval_hours": request.interval_hours,
            "start_immediately": request.start_immediately,
        },
    )
    
    return CrawlJobResponse(**job.to_dict())


@router.post("/jobs/{job_id}/unschedule", response_model=CrawlJobResponse)
async def unschedule_crawl(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disable scheduled recurring crawls for a job.
    
    Stops future automatic crawls. Any running crawl will complete.
    """
    job = db.query(CrawlerJob).filter(CrawlerJob.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check access
    if current_user.role not in ['super_admin', 'superadmin']:
        if job.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Unschedule the job
    from app.services.crawler_scheduler import CrawlerScheduler
    
    success = CrawlerScheduler.unschedule_job(db=db, job_id=job_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to unschedule job")
    
    # Refresh job from DB
    db.refresh(job)
    
    logger.info(f"User {current_user.username} unscheduled job {job_id}")
    
    # Log activity
    activity_tracker.log_activity(
        activity_type="crawl_unscheduled",
        user=current_user.username,
        details={
            "job_id": job_id,
            "target_url": job.target_url,
            "collection_id": job.collection_id,
        },
    )
    
    return CrawlJobResponse(**job.to_dict())


@router.get("/scheduled", response_model=CrawlJobListResponse)
async def list_scheduled_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all scheduled crawl jobs.
    
    Returns jobs that have recurring schedules enabled.
    """
    query = db.query(CrawlerJob).filter(CrawlerJob.is_scheduled == True)
    
    # Filter by user unless superadmin
    if current_user.role not in ['super_admin', 'superadmin']:
        query = query.filter(CrawlerJob.user_id == current_user.user_id)
    
    # Get total and jobs
    total = query.count()
    jobs = query.order_by(CrawlerJob.next_run_at.asc()).all()
    
    return CrawlJobListResponse(
        jobs=[CrawlJobResponse(**job.to_dict()) for job in jobs],
        total=total
    )
