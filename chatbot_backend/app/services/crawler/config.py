# app/services/crawler/config.py
"""
Crawler Configuration and Domain Rules
Production-ready configuration for the web crawler with per-domain rules.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple
from datetime import datetime
import json


@dataclass
class CrawlConfig:
    """Configuration for a crawl job."""
    
    # Target settings
    target_url: str
    collection_id: str
    
    # Crawl limits
    max_pages: int = 0  # 0 = unlimited (no default limit)
    max_depth: int = 5
    
    # Rate limiting - optimized for speed while respecting server limits
    min_delay_seconds: float = 0.2   # Reduced for faster crawling
    max_delay_seconds: float = 3.0   # Slightly increased for rate limit recovery
    concurrent_requests: int = 5     # Increased from 3 for faster crawling
    
    # Content settings
    chunk_size: int = 1000  # tokens per chunk for RAG
    chunk_overlap: int = 500  # overlap between chunks
    
    # Phase 2: Enhanced Chunking Configuration
    ENABLE_HIERARCHICAL_CHUNKING: bool = True
    ENABLE_PERSON_CHUNKING: bool = True
    ENABLE_SEMANTIC_CHUNKING: bool = True
    
    # Phase 2: Chunk sizes by content type (min, max tokens)
    CHUNK_SIZES: Dict[str, Tuple[int, int]] = field(default_factory=lambda: {
        "narrative": (800, 1200),
        "reference": (600, 800),
        "code": (400, 600),
        "person_profile": (200, 800),  # Flexible for complete profiles
    })
    
    # Phase 2: Hierarchical chunking settings
    PARENT_CHUNK_SIZE: int = 1500  # tokens
    CHILD_CHUNK_SIZE_RANGE: Tuple[int, int] = (400, 600)  # tokens
    
    # Phase 2: Semantic overlap
    SEMANTIC_OVERLAP_RATIO: float = 0.25  # 25% overlap

    # Filtering
    # NOTE:
    # - Use segment-specific patterns (e.g., "/admin/") to avoid
    #   accidentally matching common words like "administration"
    #   in paths such as "/research-administration/...".
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "/login", "/signin", "/auth", "/admin/", "/logout",
        "/cart", "/checkout", "/account", "/profile",
        "/search", "/tag/", "/category/", "/author/"
    ])
    include_keywords: List[str] = field(default_factory=list)
    
    # Content types to process
    allowed_content_types: List[str] = field(default_factory=lambda: [
        "text/html",
        "text/plain",
        "application/xhtml+xml"
    ])
    
    # Extensions to skip
    skip_extensions: Set[str] = field(default_factory=lambda: {
        ".zip", ".exe", ".dmg", ".pkg", ".rar", ".7z",
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
        ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm",
        ".xls", ".xlsx", ".ppt", ".pptx",
        ".ics", ".vcf", ".css", ".js", ".json", ".xml"
    })
    
    # Document processing
    process_documents: bool = True  # Enable/disable document processing
    document_types: Set[str] = field(default_factory=lambda: {".pdf", ".docx", ".doc"})
    max_document_size_mb: int = 100  # Skip documents larger than this
    
    # Duplicate detection
    similarity_threshold: float = 0.90  # Skip pages > 90% similar
    
    # JavaScript handling
    wait_for_js: bool = True
    scroll_page: bool = True
    click_expand_elements: bool = True
    
    # Sitemap
    use_sitemap: bool = True
    
    # LLM cleaning (optional, expensive)
    use_llm_cleaning: bool = False
    
    # Timeout settings (milliseconds)
    page_timeout_ms: int = 45000           # Initial page load timeout
    network_idle_timeout_ms: int = 15000   # Network idle wait timeout
    
    # Resilience settings for large sites
    max_retries_per_page: int = 3              # Max retries per individual page
    circuit_breaker_threshold: int = 20        # Consecutive failures to trigger pause
    circuit_breaker_reset_seconds: int = 30    # Seconds to wait before retry after circuit opens
    max_backoff_seconds: float = 60.0          # Maximum backoff delay in seconds
    stale_heartbeat_seconds: int = 300         # Consider stuck if no activity for 5 min
    
    # OCR Configuration
    enable_ocr: bool = False
    ocr_max_images_per_page: int = 20
    ocr_timeout_seconds: int = 15
    ocr_priority_threshold: int = 5
    ocr_min_confidence: float = 0.5
    ocr_cache_dir: str = "./ocr_cache"
    ocr_use_gpu: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "target_url": self.target_url,
            "collection_id": self.collection_id,
            "max_pages": self.max_pages,
            "max_depth": self.max_depth,
            "min_delay_seconds": self.min_delay_seconds,
            "max_delay_seconds": self.max_delay_seconds,
            "chunk_size": self.chunk_size,
            "exclude_patterns": self.exclude_patterns,
            "include_keywords": self.include_keywords,
            "similarity_threshold": self.similarity_threshold,
            "use_sitemap": self.use_sitemap,
            "use_llm_cleaning": self.use_llm_cleaning,
            "page_timeout_ms": self.page_timeout_ms,
            "network_idle_timeout_ms": self.network_idle_timeout_ms,
            "max_retries_per_page": self.max_retries_per_page,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
            "circuit_breaker_reset_seconds": self.circuit_breaker_reset_seconds,
            "max_backoff_seconds": self.max_backoff_seconds,
            "circuit_breaker_reset_seconds": self.circuit_breaker_reset_seconds,
            "max_backoff_seconds": self.max_backoff_seconds,
            "stale_heartbeat_seconds": self.stale_heartbeat_seconds,
            "enable_ocr": self.enable_ocr,
            "ocr_max_images_per_page": self.ocr_max_images_per_page,
            "ocr_min_confidence": self.ocr_min_confidence
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CrawlConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CrawlStats:
    """Statistics for a crawl job."""
    
    job_id: str
    target_url: str
    status: str = "pending"  # pending, running, completed, failed, cancelled
    
    # Progress
    pages_discovered: int = 0
    pages_crawled: int = 0
    pages_skipped: int = 0
    pages_failed: int = 0
    
    # Content stats
    chunks_created: int = 0
    total_characters: int = 0
    
    # OCR Statistics
    images_analyzed: int = 0
    images_ocr_attempted: int = 0
    images_ocr_succeeded: int = 0
    images_ocr_failed: int = 0
    ocr_text_extracted: int = 0
    ocr_people_found: int = 0
    total_ocr_time: float = 0.0
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Errors
    error_message: Optional[str] = None
    
    # Current activity
    current_url: Optional[str] = None
    
    # URL tracking
    crawled_urls: List[Dict] = field(default_factory=list)  # [{url, chunks, title}]
    failed_urls: List[Dict] = field(default_factory=list)   # [{url, reason}]
    skipped_urls: List[Dict] = field(default_factory=list)  # [{url, reason}]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "job_id": self.job_id,
            "target_url": self.target_url,
            "status": self.status,
            "pages_discovered": self.pages_discovered,
            "pages_crawled": self.pages_crawled,
            "pages_skipped": self.pages_skipped,
            "pages_failed": self.pages_failed,
            "chunks_created": self.chunks_created,
            "total_characters": self.total_characters,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "current_url": self.current_url,
            "progress_percent": self._calculate_progress()
        }
    
    def _calculate_progress(self) -> int:
        """Calculate progress percentage."""
        if self.status == "completed":
            return 100
        if self.status == "pending":
            return 0
        if self.pages_discovered == 0:
            return 5  # Started but no pages discovered yet
        return min(95, int((self.pages_crawled / max(self.pages_discovered, 1)) * 100))


# User-Agent rotation list for anti-bot protection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]
