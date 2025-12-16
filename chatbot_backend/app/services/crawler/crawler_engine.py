# app/services/crawler/crawler_engine.py
"""
Crawler Engine
Production-ready web crawler with Playwright browser automation.
Enhanced for SPA/JS-rendered sites with URL validation and fuzzy correction.
"""

import asyncio
import random
import time
import re
import logging
import os
import tempfile
import shutil
from typing import Set, List, Dict, Optional, Callable
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

# Fuzzy matching for URL correction
try:
    from rapidfuzz import process, fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

from .config import CrawlConfig, CrawlStats, USER_AGENTS
from .content_extractor import ContentExtractor
from .chunker import TextChunker, ContentChunk
from .duplicate_detector import DuplicateDetector
from .sitemap_parser import SitemapParser
from .html_fetcher import fetch_static, is_empty_static, close_playwright
from .document_extractor import download_document, extract_text_from_document, is_document_url

logger = logging.getLogger("crawler_engine")

# Module-level set of canonical URL path segments for fuzzy correction
# Populated as valid URLs are discovered during crawling
CANONICAL_SEGMENTS: Set[str] = set()


def is_invalid_url(url: str) -> bool:
    """
    Validate URL to reject malformed or non-crawlable links.
    
    This catches:
    - Non-HTTP schemes (javascript:, mailto:, tel:, data:)
    - Anchor-only links (#)
    - URLs with 3+ repeated characters (e.g., "ttime", "soources")
    - Segments starting with repeated letters (e.g., "ppolicies", "aapple")
    - Unusual double-letter patterns not common in English
    
    Returns:
        True if URL should be skipped (is invalid)
    """
    # Reject non-http schemes
    if url.startswith(("javascript:", "mailto:", "tel:", "data:", "#")):
        return True
    
    # Extract path for pattern checks
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
    except Exception:
        return True
    
    # Reject 3+ repeated characters anywhere (e.g., "ttime" has "ttt" pattern is wrong, 
    # but we check for any char repeated 3+ times like "aaa", "bbb")
    if re.search(r"(.)\1{2,}", path):
        return True
    
    # Check each path segment for malformed patterns
    segments = path.strip("/").split("/")
    for segment in segments:
        if not segment:
            continue
        
        # Reject segments starting with repeated letter (e.g., "ppolicies", "aapple", "bbenefits")
        if len(segment) >= 2 and segment[0] == segment[1]:
            # Very few English words start with doubled letters
            valid_double_starts = {"aa", "ee", "oo"}
            if segment[:2] not in valid_double_starts:
                logger.debug(f"🚫 Rejecting URL with doubled start: {segment} in {url}")
                return True
        
        # Reject unusual double-letter patterns within segment
        # Common valid double letters in English
        common_doubles = {
            "ss", "tt", "ll", "oo", "ee", "ff", "rr", "nn", 
            "pp", "cc", "mm", "dd", "gg", "bb", "aa", "ii", "zz", "ww"
        }
        
        double_matches = re.findall(r"([a-z])\1", segment)
        for match in double_matches:
            double = match + match
            if double not in common_doubles:
                logger.debug(f"🚫 Rejecting URL with unusual double: {double} in {url}")
                return True
    
    return False


def add_canonical_segments(url: str):
    """
    Extract and store canonical path segments from a known-good URL.
    These are used for fuzzy correction of potentially misspelled URLs.
    """
    try:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        for p in parts:
            # Only add meaningful segments (not numbers or very short)
            if len(p) > 2 and not re.match(r"^\d+$", p):
                CANONICAL_SEGMENTS.add(p.lower())
    except Exception:
        pass


def fuzzy_fix_segment(segment: str) -> str:
    """
    Attempt to correct a potentially misspelled URL segment using fuzzy matching.
    
    Only applies when rapidfuzz is available and we have canonical segments to compare against.
    
    Args:
        segment: URL path segment to potentially correct
        
    Returns:
        Corrected segment if high-confidence match found, otherwise original
    """
    if not RAPIDFUZZ_AVAILABLE or not CANONICAL_SEGMENTS:
        return segment
    
    segment_lower = segment.lower()
    
    # If already known, no correction needed
    if segment_lower in CANONICAL_SEGMENTS:
        return segment
    
    try:
        match = process.extractOne(
            segment_lower,
            CANONICAL_SEGMENTS,
            scorer=fuzz.ratio
        )
        
        if match and match[1] > 85:  # High confidence threshold
            logger.debug(f"🔧 Fuzzy corrected '{segment}' → '{match[0]}' (score: {match[1]})")
            return match[0]
    except Exception:
        pass
    
    return segment


def fuzzy_fix_url(url: str) -> str:
    """
    Attempt to fix a potentially misspelled URL by correcting each path segment.
    
    Args:
        url: Full URL to potentially correct
        
    Returns:
        Corrected URL if segments were fixed, otherwise original
    """
    if not RAPIDFUZZ_AVAILABLE or not CANONICAL_SEGMENTS:
        return url
    
    try:
        parsed = urlparse(url)
        segments = parsed.path.strip("/").split("/")
        
        corrected_segments = []
        was_corrected = False
        
        for seg in segments:
            if seg:
                fixed = fuzzy_fix_segment(seg)
                if fixed != seg.lower():
                    was_corrected = True
                corrected_segments.append(fixed)
        
        if was_corrected:
            new_path = "/" + "/".join(corrected_segments)
            corrected = urlunparse((
                parsed.scheme,
                parsed.netloc,
                new_path,
                parsed.params,
                parsed.query,
                ""
            ))
            logger.info(f"🔧 Fuzzy corrected URL: {url} → {corrected}")
            return corrected
    except Exception:
        pass
    
    return url




class CrawlerEngine:
    """
    Production-ready web crawler with:
    - Playwright browser automation
    - Semantic content extraction
    - Duplicate detection
    - Sitemap support
    - Rate limiting & backpressure
    - Progress callbacks
    """
    
    def __init__(
        self,
        config: CrawlConfig,
        on_progress: Optional[Callable[[CrawlStats], None]] = None,
        on_chunk: Optional[Callable[[ContentChunk], None]] = None
    ):
        """
        Initialize crawler engine.
        
        Args:
            config: Crawl configuration
            on_progress: Callback for progress updates
            on_chunk: Callback when a chunk is ready for embedding
        """
        self.config = config
        self.on_progress = on_progress
        self.on_chunk = on_chunk
        
        # Parse base URL
        self.parsed_url = urlparse(config.target_url)
        self.domain = f"{self.parsed_url.scheme}://{self.parsed_url.netloc}"
        
        # Initialize components
        self.content_extractor = ContentExtractor()
        self.chunker = TextChunker(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        self.duplicate_detector = DuplicateDetector(
            similarity_threshold=config.similarity_threshold
        )
        self.sitemap_parser = SitemapParser(config.target_url)
        
        # URL tracking
        self.visited_urls: Set[str] = set()
        self.to_visit: List[tuple] = []  # (url, depth) tuples
        self.failed_urls: List[Dict] = []
        
        # Robots.txt
        self.robots_parser: Optional[RobotFileParser] = None
        
        # Stats
        self.stats = CrawlStats(
            job_id="",
            target_url=config.target_url
        )
        
        # Rate limiting state
        self.current_delay = config.min_delay_seconds
        self.consecutive_errors = 0
        
        # Collected chunks
        self.chunks: List[ContentChunk] = []
        
        # Cancellation flag
        self._cancelled = False
        
        # Temporary directory for document downloads
        self.temp_download_dir = None
    
    def cancel(self):
        """Cancel the ongoing crawl."""
        self._cancelled = True
        logger.info("Crawl cancellation requested")
    
    async def crawl(self, job_id: str) -> CrawlStats:
        """
        Execute the crawl.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            CrawlStats with final statistics
        """
        self.stats.job_id = job_id
        self.stats.status = "running"
        self.stats.started_at = datetime.utcnow()
        
        self._notify_progress()
        
        try:
            # 1. Load robots.txt
            self._load_robots()
            
            # 2. Discover URLs from sitemap if enabled
            if self.config.use_sitemap:
                self._discover_from_sitemap()
            
            # 3. Add start URL
            self._add_url_to_visit(self.config.target_url, depth=0)
            
            # 4. Start browser and crawl
            await self._run_browser_crawl()
            
            # 5. Mark complete
            if self._cancelled:
                self.stats.status = "cancelled"
            else:
                self.stats.status = "completed"
            
        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            self.stats.status = "failed"
            self.stats.error_message = str(e)
        finally:
            # Cleanup Playwright browser context
            try:
                close_playwright()
            except Exception:
                pass
            
            # Cleanup temporary download directory
            if self.temp_download_dir and os.path.exists(self.temp_download_dir):
                try:
                    shutil.rmtree(self.temp_download_dir)
                    logger.info(f"Cleaned up temp directory: {self.temp_download_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory: {e}")
        
        self.stats.completed_at = datetime.utcnow()
        self._notify_progress()
        
        return self.stats
    
    def _load_robots(self):
        """Load and parse robots.txt."""
        try:
            robots_url = urljoin(self.domain, '/robots.txt')
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()
            logger.info(f"Loaded robots.txt from {robots_url}")
        except Exception as e:
            logger.debug(f"Could not load robots.txt: {e}")
    
    def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched per robots.txt."""
        if self.robots_parser is None:
            return True
        try:
            return self.robots_parser.can_fetch("*", url)
        except Exception:
            return True
    
    def _discover_from_sitemap(self):
        """Discover URLs from sitemap."""
        try:
            sitemap_urls = self.sitemap_parser.discover_and_parse()
            
            for sitemap_url in sitemap_urls:
                if self._should_crawl_url(sitemap_url.loc):
                    self._add_url_to_visit(sitemap_url.loc, depth=1)
            
            self.stats.pages_discovered = len(self.to_visit)
            logger.info(f"Discovered {len(sitemap_urls)} URLs from sitemap")
            
        except Exception as e:
            logger.warning(f"Sitemap discovery failed: {e}")
    
    def _should_crawl_url(self, url: str) -> bool:
        """Check if URL should be crawled based on config and validation."""
        # First, reject obviously malformed URLs (typos, bad schemes, etc.)
        if is_invalid_url(url):
            return False
        
        # Check if internal
        parsed = urlparse(url)
        if parsed.netloc and parsed.netloc != self.parsed_url.netloc:
            return False
        
        # Check extension
        path = parsed.path.lower()
        for ext in self.config.skip_extensions:
            if path.endswith(ext):
                return False
        
        # Check exclude patterns
        for pattern in self.config.exclude_patterns:
            if pattern in path.lower():
                return False
        
        # Check include keywords (if specified)
        if self.config.include_keywords:
            has_keyword = any(kw.lower() in path.lower() for kw in self.config.include_keywords)
            if not has_keyword:
                return False
        
        # Check robots.txt
        if not self._can_fetch(url):
            return False
        
        return True
    
    def _add_url_to_visit(self, url: str, depth: int):
        """Add URL to visit queue if not visited."""
        normalized = self._normalize_url(url)
        
        if normalized in self.visited_urls:
            return
        
        if depth > self.config.max_depth:
            return
        
        self.to_visit.append((normalized, depth))
        self.stats.pages_discovered = max(
            self.stats.pages_discovered,
            len(self.to_visit) + len(self.visited_urls)
        )
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison and validation."""
        try:
            parsed = urlparse(url)
            
            # Prefer https for same-host http links to reduce duplicates
            scheme = parsed.scheme
            if parsed.scheme == "http" and parsed.netloc.lower() == self.parsed_url.netloc.lower():
                scheme = "https"
            
            # Normalize path: remove double slashes, trailing slashes
            path = parsed.path
            # Remove double slashes
            while '//' in path:
                path = path.replace('//', '/')

            # Fix common typos seen on MIT policies links
            typo_map = {
                "proocedures": "procedures",
                "procedurres": "procedures",
                "proceduures": "procedures",
                "proceduure": "procedure",
                "policcy": "policy",
                "ppolicy": "policy",
                "policyy": "policy",
                "policyy-": "policy-",
            }
            for bad, good in typo_map.items():
                if bad in path:
                    path = path.replace(bad, good)
            # Ensure path starts with /
            if not path:
                path = '/'
            # Remove trailing slash (except root)
            if path != '/' and path.endswith('/'):
                path = path.rstrip('/')
            
            normalized = urlunparse((
                scheme,
                parsed.netloc.lower(),
                path,
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            return normalized
        except Exception:
            return url

    def _maybe_autocorrect_and_queue(self, url: str, depth: int) -> bool:
        """
        DISABLED: This function was collapsing ALL double letters in URLs,
        destroying valid English words like:
        - committees -> comites
        - appointments -> apointments
        - professional -> profesional
        
        This caused massive 404 failures. URL typo correction is now handled
        only via the explicit typo_map in _normalize_url().
        """
        return False
    
    async def _run_browser_crawl(self):
        """Run the browser-based crawl with concurrent page processing."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install chromium")
            raise RuntimeError("Playwright not installed")
        
        # Concurrency settings - use 5 concurrent pages for faster crawling
        max_concurrent = getattr(self.config, 'concurrent_requests', 5) or 5
        semaphore = asyncio.Semaphore(max_concurrent)
        
        logger.info(f"Starting crawl with {max_concurrent} concurrent workers")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=random.choice(USER_AGENTS),
                ignore_https_errors=True
            )
            
            try:
                # Track active tasks for cleanup
                active_tasks = set()
                
                # Worker function to process a single URL
                async def process_url_worker(url: str, depth: int):
                    async with semaphore:
                        if self._cancelled:
                            return
                        
                        # Check limit BEFORE processing - atomic check
                        if self.config.max_pages > 0 and self.stats.pages_crawled >= self.config.max_pages:
                            return
                        
                        # Create a new page for this worker
                        page = await context.new_page()
                        
                        # Handle downloads by cancelling them (we don't process files yet)
                        page.on("download", lambda download: download.cancel())
                        
                        try:
                            # Check limit again right before processing (double-check for race conditions)
                            if self.config.max_pages > 0 and self.stats.pages_crawled >= self.config.max_pages:
                                return
                            
                            self.stats.current_url = url
                            success = await self._process_page(page, url, depth)
                            
                            if success:
                                # Atomically check and increment - only increment if under limit
                                if self.config.max_pages == 0 or self.stats.pages_crawled < self.config.max_pages:
                                    self.stats.pages_crawled += 1
                                    self.consecutive_errors = 0
                                    self._decrease_delay()  # Speed up on success
                                else:
                                    # Limit reached during processing, don't count this page
                                    logger.debug(f"Skipping page count for {url} - limit reached during processing")
                            else:
                                self.stats.pages_failed += 1
                                self.consecutive_errors += 1
                                if self.consecutive_errors >= 5:
                                    self._increase_delay()
                            
                            self._notify_progress()
                            
                            # Adaptive delay - reduce delay when successful
                            delay = max(0.2, self.current_delay / max_concurrent)
                            await asyncio.sleep(delay)
                        except Exception as e:
                            # Log but don't crash - continue with other URLs
                            logger.error(f"Worker error processing {url}: {e}")
                            self.stats.pages_failed += 1
                        finally:
                            try:
                                await page.close()
                            except Exception:
                                pass
                
                # Process URLs - continue until all processed or limits reached
                processed_count = 0
                while not self._cancelled:
                    # Check limits - skip if max_pages is 0 (unlimited)
                    if self.config.max_pages > 0 and self.stats.pages_crawled >= self.config.max_pages:
                        logger.info(f"Reached max pages limit: {self.config.max_pages}")
                        break
                    
                    # If no more URLs to process, we're done
                    if not self.to_visit:
                        # Wait a moment for any new URLs from in-progress pages
                        await asyncio.sleep(0.5)
                        if not self.to_visit:
                            logger.info("No more URLs to process")
                            break
                    
                    # Calculate how many pages we can still crawl
                    remaining_pages = float('inf')
                    if self.config.max_pages > 0:
                        remaining_pages = self.config.max_pages - self.stats.pages_crawled
                        if remaining_pages <= 0:
                            logger.info(f"Reached max pages limit: {self.config.max_pages}")
                            break
                    
                    # Get batch of URLs to process - limit batch size to remaining pages
                    max_batch_size = min(max_concurrent * 2, len(self.to_visit))
                    if self.config.max_pages > 0:
                        max_batch_size = min(max_batch_size, int(remaining_pages))
                    
                    batch = []
                    
                    for _ in range(max_batch_size):
                        if not self.to_visit:
                            break
                        # Check limit before adding to batch
                        if self.config.max_pages > 0 and self.stats.pages_crawled >= self.config.max_pages:
                            break
                        url, depth = self.to_visit.pop(0)
                        if url not in self.visited_urls:
                            self.visited_urls.add(url)
                            batch.append((url, depth))
                    
                    if not batch:
                        continue
                    
                    # Process batch concurrently - use return_exceptions to not fail on single errors
                    tasks = [process_url_worker(url, depth) for url, depth in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Log any exceptions (but continue processing)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            logger.warning(f"Batch task failed: {result}")
                    
                    processed_count += len(batch)
                    
                    # Log progress periodically
                    if processed_count % 50 == 0:
                        logger.info(f"Progress: {self.stats.pages_crawled} crawled, {self.stats.pages_failed} failed, {len(self.to_visit)} queued")
                    
            finally:
                await browser.close()

    
    async def _process_document(self, url: str, depth: int) -> bool:
        """
        Process a document (PDF or DOCX) by downloading and extracting text.
        
        Args:
            url: Document URL
            depth: Current crawl depth
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create temp directory if needed
            if not self.temp_download_dir:
                self.temp_download_dir = tempfile.mkdtemp(prefix="crawler_docs_")
                logger.info(f"Created temp directory: {self.temp_download_dir}")
            
            logger.info(f"Processing document: {url}")
            
            # Download the document
            loop = asyncio.get_event_loop()
            file_path = await loop.run_in_executor(None, download_document, url, self.temp_download_dir)
            
            if not file_path:
                logger.warning(f"Failed to download document: {url}")
                self.stats.failed_urls.append({"url": url, "reason": "Document download failed"})
                return False
            
            # Extract text from document
            extracted = await loop.run_in_executor(None, extract_text_from_document, file_path, url)
            
            # Check if extraction was successful
            if not extracted.get('raw_text') or len(extracted['raw_text'].strip()) < 50:
                logger.warning(f"No content extracted from document: {url}")
                self.stats.skipped_urls.append({"url": url, "reason": "No text content in document"})
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                return False
            
            # Check for duplicates
            is_dup, reason = self.duplicate_detector.is_duplicate(url, extracted['raw_text'], extracted.get('title', ''))
            
            if is_dup:
                logger.debug(f"Skipping duplicate document: {url} ({reason})")
                self.stats.pages_skipped += 1
                self.stats.skipped_urls.append({"url": url, "reason": f"Duplicate: {reason}"})
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                return False
            
            # Create chunks
            page_chunks = self.chunker.chunk_page(extracted, job_id=self.stats.job_id, collection_id=self.config.collection_id, crawl_depth=depth)
            
            # Process chunks
            for chunk in page_chunks:
                self.chunks.append(chunk)
                self.stats.chunks_created += 1
                self.stats.total_characters += chunk.char_count
                if self.on_chunk:
                    self.on_chunk(chunk)
            
            # Track successfully processed document
            self.stats.crawled_urls.append({"url": url, "title": extracted.get('title', '')[:100], "chunks": len(page_chunks)})
            logger.info(f"✅ Document processed: {url} ({len(page_chunks)} chunks)")
            
            # Clean up the downloaded file
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup document file: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing document {url}: {e}")
            self.stats.failed_urls.append({"url": url, "reason": f"Document processing error: {str(e)[:100]}"})
            return False
    
    async def _process_page(self, page, url: str, depth: int, retry_count: int = 0) -> bool:
        """
        Process a single page with retry mechanism.
        
        Args:
            page: Playwright page object
            url: URL to process
            depth: Current crawl depth
            retry_count: Current retry attempt (0-2)
            
        Returns:
            True if successful, False otherwise
        """
        # Check if this is a document URL (PDF/DOCX)
        if self.config.process_documents and is_document_url(url):
            return await self._process_document(url, depth)
        # HYBRID FETCH: Try static fetch first (fast), fallback to Playwright for SPAs
        # This optimizes crawl speed by avoiding browser overhead for static sites
        use_static_html = False
        html_content = None
        response = None  # Will be set if Playwright is used
        
        if retry_count == 0:  # Only try static on first attempt
            try:
                loop = asyncio.get_event_loop()
                static_html = await loop.run_in_executor(None, fetch_static, url)
                
                # is_empty_static returns (is_empty: bool, reason: str)
                is_empty, reason = is_empty_static(static_html)
                
                if not is_empty:
                    logger.debug(f"Using static HTML for: {url}")
                    html_content = static_html
                    use_static_html = True
                else:
                    logger.info(f"Static HTML insufficient ({reason}) -> Using JS rendering for: {url}")
            except Exception as e:
                logger.debug(f"Static fetch pre-check failed for {url}: {e}")
        
        # Define fallback strategies: try different wait conditions and timeouts
        strategies = [
            ('networkidle', 30000),  # First try: wait for network idle, 30s
            ('domcontentloaded', 20000),  # Fallback 1: DOM ready, 20s
            ('load', 15000),  # Fallback 2: basic load, 15s
        ]
        
        current_strategy = strategies[min(retry_count, len(strategies) - 1)]
        wait_until, timeout = current_strategy
        
        try:
            # Only navigate with Playwright if static fetch didn't work
            if not use_static_html:
                # Navigate with current strategy
                logger.debug(f"Processing {url} (attempt {retry_count + 1}, wait_until={wait_until}, timeout={timeout}ms)")
                response = await page.goto(url, wait_until=wait_until, timeout=timeout)
                
                # Check for rate limiting (HTTP 429)
                if response and response.status == 429:
                    logger.warning(f"Rate limited on {url}, waiting before retry...")
                    await asyncio.sleep(5)  # Wait 5 seconds before retry
                    if retry_count < 2:
                        return await self._process_page(page, url, depth, retry_count + 1)
                    self.failed_urls.append({
                        "url": url,
                        "reason": "Rate limited (HTTP 429)"
                    })
                    return False
                
                # Check for server errors (5xx) - may be temporary
                if response and response.status >= 500:
                    logger.warning(f"Server error {response.status} on {url}")
                    if retry_count < 2:
                        await asyncio.sleep(2)  # Brief wait before retry
                        return await self._process_page(page, url, depth, retry_count + 1)
                    self.failed_urls.append({
                        "url": url,
                        "reason": f"HTTP {response.status}"
                    })
                    return False
                
                # Check for client errors (4xx) - don't retry these
                if response and response.status >= 400:
                    self.failed_urls.append({
                        "url": url,
                        "reason": f"HTTP {response.status}"
                    })
                    return False
                
                # ============================================================
                # SPA HYDRATION WAIT SEQUENCE
                # Critical for React, Angular, Vue, Next.js and other JS apps
                # ============================================================
                
                # 1. Wait for network to become idle (SPA hydration typically involves XHR/fetch)
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    logger.debug(f"✅ Network idle for {url}")
                except Exception:
                    logger.debug(f"⚠️ Network did not become idle for {url}, continuing...")
                
                # 2. Wait for main content container (Next.js/React typically render into <main>)
                try:
                    await page.wait_for_selector("main", timeout=8000)
                    logger.debug(f"✅ Found <main> element for {url}")
                except Exception:
                    # Fallback to body if no main element
                    try:
                        await page.wait_for_selector("body", timeout=3000)
                    except Exception:
                        pass
                
                # 3. Ensure DOM has stable, rendered href links (catches lazy-loaded navs)
                try:
                    await page.wait_for_function(
                        "() => document.querySelectorAll('a[href]').length > 5",
                        timeout=5000
                    )
                    logger.debug(f"✅ Stable links detected for {url}")
                except Exception:
                    logger.debug(f"⚠️ Could not verify stable links for {url}")
                
                # 4. Additional stabilization wait
                await page.wait_for_timeout(800)

                # 5. Ensure minimal content is loaded
                try:
                    await page.wait_for_function("document.body.innerText.length > 200", timeout=5000)
                except Exception:
                    logger.warning(f"Page content low after hydration for {url}")
                
                # Scroll if enabled (to trigger lazy loading)
                if self.config.scroll_page:
                    await self._scroll_page(page)
                
                # Click expand elements if enabled
                if self.config.click_expand_elements:
                    await self._click_expand_elements(page)
                
                # Get HTML content from Playwright
                html_content = await page.content()
            
            # Check content type from response
            if response:
                content_type = response.headers.get('content-type', '') if response.headers else ''
                if content_type and not any(ct in content_type for ct in self.config.allowed_content_types):
                    self.stats.pages_skipped += 1
                    return False
            
            # Extract content
            extracted = self.content_extractor.extract(html_content, url)

            # Always attempt link extraction, even if content is thin.
            # This prevents early termination on landing pages that have sparse text but valid links.
            if not use_static_html and page:
                links = await self._extract_links_from_page(page, url)
            else:
                links = self._extract_links(html_content, url)
            for link in links:
                if self._should_crawl_url(link):
                    self._add_url_to_visit(link, depth + 1)

            # If content is still insufficient, try a body innerText fallback before giving up
            raw_text = extracted.get('raw_text', '') or ''
            if (not raw_text or len(raw_text.strip()) < 80) and page:
                try:
                    fallback_text = await page.inner_text("body")
                    if fallback_text and len(fallback_text.strip()) > len(raw_text.strip()):
                        extracted['raw_text'] = fallback_text
                        raw_text = fallback_text
                        if not extracted.get('title'):
                            extracted['title'] = await page.title()
                except Exception:
                    pass

            # If still no text at all, keep links but skip chunking
            if not raw_text or len(raw_text.strip()) == 0:
                self.stats.pages_skipped += 1
                self.stats.skipped_urls.append({
                    "url": url,
                    "reason": "No content after JS rendering"
                })
                logger.warning(f"⚠️ No content after rendering, links retained: {url}")
                # Don't re-queue pages with no content - they won't have content on retry
                # This prevents infinite loops and wasted processing
                return False
            
            # Page has content - add its segments to canonical set for fuzzy matching
            add_canonical_segments(url)
            
            # Check for duplicates
            is_dup, reason = self.duplicate_detector.is_duplicate(
                url,
                extracted['raw_text'],
                extracted.get('title', '')
            )
            
            if is_dup:
                logger.debug(f"Skipping duplicate: {url} ({reason})")
                self.stats.pages_skipped += 1
                self.stats.skipped_urls.append({"url": url, "reason": f"Duplicate: {reason}"})
                return False
            
            # Create chunks
            page_chunks = self.chunker.chunk_page(
                extracted,
                job_id=self.stats.job_id,
                collection_id=self.config.collection_id,
                crawl_depth=depth
            )
            
            # Process chunks
            for chunk in page_chunks:
                self.chunks.append(chunk)
                self.stats.chunks_created += 1
                self.stats.total_characters += chunk.char_count
                
                # Callback for immediate processing
                if self.on_chunk:
                    self.on_chunk(chunk)
            
            # Track successfully crawled URL
            self.stats.crawled_urls.append({
                "url": url,
                "title": extracted.get('title', '')[:100],
                "chunks": len(page_chunks)
            })
            
            return True
            
        except asyncio.TimeoutError as e:
            # Timeout - try with fallback strategy
            logger.warning(f"Timeout on {url} (attempt {retry_count + 1}): {e}")
            if retry_count < 2:
                return await self._process_page(page, url, depth, retry_count + 1)
            self.stats.failed_urls.append({
                "url": url,
                "reason": f"Timeout after {retry_count + 1} attempts"
            })
            return False
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for download error (Playwright)
            if "Download is starting" in error_msg:
                logger.info(f"Skipping file download: {url}")
                self.stats.pages_skipped += 1
                self.stats.skipped_urls.append({
                    "url": url,
                    "reason": "File download (PDF/Doc)"
                })
                # Decrement failure count since this is expected for files
                if retry_count == 0:
                   self.stats.pages_failed = max(0, self.stats.pages_failed) 
                return False

            logger.warning(f"Error processing {url} (attempt {retry_count + 1}): {error_msg[:100]}")
            
            # Retry for certain recoverable errors
            if retry_count < 2 and any(err in error_msg.lower() for err in ['timeout', 'connection', 'network', 'navigation']):
                await asyncio.sleep(1)  # Brief pause before retry
                return await self._process_page(page, url, depth, retry_count + 1)
            
            self.stats.failed_urls.append({
                "url": url,
                "reason": error_msg[:200]
            })
            return False
    
    async def _scroll_page(self, page):
        """Scroll page to trigger lazy loading."""
        try:
            await page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 500;
                        const timer = setInterval(() => {
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= document.body.scrollHeight || totalHeight > 5000) {
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                    window.scrollTo(0, 0);
                }
            """)
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.debug(f"Scroll failed: {e}")
    
    async def _click_expand_elements(self, page):
        """Click common "expand" or "read more" elements."""
        expand_selectors = [
            '.read-more', '.show-more', '.expand', '.expand-section',
            '[aria-expanded="false"]', '.accordion-toggle',
            'button:has-text("Read more")', 'button:has-text("Show more")'
        ]
        
        for selector in expand_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements[:5]:  # Limit to prevent too many clicks
                    try:
                        await element.click(timeout=1000)
                        await page.wait_for_timeout(200)
                    except Exception:
                        pass
            except Exception:
                pass
    
    async def _extract_links_from_page(self, page, current_url: str) -> Set[str]:
        """
        Extract internal links DIRECTLY from the Playwright rendered DOM.
        
        This method extracts links from the actual rendered page, not from
        static HTML. This ensures we capture dynamically generated links.
        
        Args:
            page: Playwright page object
            current_url: Current page URL for resolving relative links
            
        Returns:
            Set of normalized internal URLs
        """
        links = set()
        skipped_external = 0
        skipped_invalid = 0
        
        try:
            # Extract all anchor elements with href from the rendered DOM
            elements = await page.query_selector_all("a[href]")
            
            for el in elements:
                try:
                    href = await el.get_attribute("href")
                    
                    if not href:
                        continue
                    
                    href = href.strip()
                    
                    # Skip invalid link types
                    if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:')):
                        skipped_invalid += 1
                        continue
                    
                    # Normalize to absolute URL using urljoin
                    absolute_url = urljoin(current_url, href)
                    normalized = self._normalize_url(absolute_url)
                    
                    # Check if internal (same domain only)
                    parsed = urlparse(normalized)
                    if parsed.netloc == self.parsed_url.netloc:
                        links.add(normalized)
                        # Log each discovered link for debugging
                        logger.debug(f"  → Found: {normalized}")
                    else:
                        skipped_external += 1
                        
                except Exception as e:
                    logger.debug(f"Error getting href from element: {e}")
                    continue
            
            # Summary log
            logger.info(f"🔗 Discovered {len(links)} internal links from {current_url} (skipped: {skipped_external} external, {skipped_invalid} invalid)")
                    
        except Exception as e:
            logger.warning(f"⚠️ Error extracting links from Playwright DOM for {current_url}: {e}")
        
        return links
    
    def _extract_links(self, html_content: str, current_url: str) -> Set[str]:
        """
        Extract internal links from HTML using BeautifulSoup (fallback for static HTML).
        
        Note: For rendered pages, use _extract_links_from_page() instead.
        """
        links = set()
        skipped_external = 0
        skipped_invalid = 0
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for anchor in soup.find_all('a', href=True):
                href = anchor.get('href', '').strip()
                
                if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                    skipped_invalid += 1
                    continue
                
                absolute_url = urljoin(current_url, href)
                normalized = self._normalize_url(absolute_url)
                
                # Check if internal
                parsed = urlparse(normalized)
                if parsed.netloc == self.parsed_url.netloc:
                    links.add(normalized)
                    logger.debug(f"  → Found (static): {normalized}")
                else:
                    skipped_external += 1
            
            if links:
                logger.info(f"🔗 Discovered {len(links)} internal links (static) from {current_url} (skipped: {skipped_external} external, {skipped_invalid} invalid)")
                    
        except Exception as e:
            logger.warning(f"⚠️ Error extracting links from static HTML for {current_url}: {e}")
        
        return links
    
    def _increase_delay(self):
        """Increase delay due to errors (backpressure)."""
        if self.consecutive_errors >= 3:
            self.current_delay = min(
                self.current_delay * 1.5,
                self.config.max_delay_seconds * 2
            )
            # Only log if delay actually changed significantly or hit max
            if self.current_delay < self.config.max_delay_seconds * 2:
                logger.debug(f"Increased delay to {self.current_delay:.1f}s due to errors")
    
    def _decrease_delay(self):
        """Decrease delay on success."""
        self.current_delay = max(
            self.current_delay * 0.9,
            self.config.min_delay_seconds
        )
    
    def _notify_progress(self):
        """Send progress update via callback."""
        if self.on_progress:
            try:
                self.on_progress(self.stats)
            except Exception as e:
                logger.debug(f"Progress callback error: {e}")
    
    def get_chunks(self) -> List[ContentChunk]:
        """Get all collected chunks."""
        return self.chunks
    
    def get_stats(self) -> CrawlStats:
        """Get current statistics."""
        return self.stats
