# app/services/crawler/crawler_engine.py
"""
Crawler Engine
Production-ready web crawler with Playwright browser automation.
"""

import asyncio
import random
import time
import re
import logging
from typing import Set, List, Dict, Optional, Callable
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .config import CrawlConfig, CrawlStats, USER_AGENTS
from .content_extractor import ContentExtractor
from .chunker import TextChunker, ContentChunk
from .duplicate_detector import DuplicateDetector
from .sitemap_parser import SitemapParser

logger = logging.getLogger("crawler_engine")


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
        """Check if URL should be crawled based on config."""
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
        """Normalize URL for comparison."""
        try:
            parsed = urlparse(url)
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path.rstrip('/') or '/',
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            return normalized
        except Exception:
            return url
    
    async def _run_browser_crawl(self):
        """Run the browser-based crawl with concurrent page processing."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install chromium")
            raise RuntimeError("Playwright not installed")
        
        # Concurrency settings - use 3 concurrent pages by default
        max_concurrent = getattr(self.config, 'concurrent_requests', 3) or 3
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=random.choice(USER_AGENTS)
            )
            
            try:
                # Worker function to process a single URL
                async def process_url_worker(url: str, depth: int):
                    async with semaphore:
                        if self._cancelled:
                            return
                        if self.stats.pages_crawled >= self.config.max_pages:
                            return
                        
                        # Create a new page for this worker
                        page = await context.new_page()
                        try:
                            self.stats.current_url = url
                            success = await self._process_page(page, url, depth)
                            
                            if success:
                                self.stats.pages_crawled += 1
                                self.consecutive_errors = 0
                            else:
                                self.stats.pages_failed += 1
                                self.consecutive_errors += 1
                            
                            self._notify_progress()
                            
                            # Reduced delay for concurrent crawling
                            await asyncio.sleep(max(0.3, self.current_delay / 2))
                        finally:
                            await page.close()
                
                # Process URLs in batches for better control
                while self.to_visit and not self._cancelled:
                    # Check limits
                    if self.stats.pages_crawled >= self.config.max_pages:
                        logger.info(f"Reached max pages limit: {self.config.max_pages}")
                        break
                    
                    # Get batch of URLs to process
                    batch_size = min(max_concurrent, len(self.to_visit))
                    batch = []
                    
                    for _ in range(batch_size):
                        if not self.to_visit:
                            break
                        url, depth = self.to_visit.pop(0)
                        if url not in self.visited_urls:
                            self.visited_urls.add(url)
                            batch.append((url, depth))
                    
                    if not batch:
                        continue
                    
                    # Process batch concurrently
                    tasks = [process_url_worker(url, depth) for url, depth in batch]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
            finally:
                await browser.close()
    
    async def _process_page(self, page, url: str, depth: int) -> bool:
        """
        Process a single page.
        
        Args:
            page: Playwright page object
            url: URL to process
            depth: Current crawl depth
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Navigate with timeout
            response = await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Check status
            if response and response.status >= 400:
                self.failed_urls.append({
                    "url": url,
                    "reason": f"HTTP {response.status}"
                })
                return False
            
            # Wait for content
            await page.wait_for_timeout(1000)
            
            # Scroll if enabled (to trigger lazy loading)
            if self.config.scroll_page:
                await self._scroll_page(page)
            
            # Click expand elements if enabled
            if self.config.click_expand_elements:
                await self._click_expand_elements(page)
            
            # Get HTML content
            html_content = await page.content()
            
            # Check content type from response
            if response:
                content_type = response.headers.get('content-type', '') if response.headers else ''
                if content_type and not any(ct in content_type for ct in self.config.allowed_content_types):
                    self.stats.pages_skipped += 1
                    return False
            
            # Extract content
            extracted = self.content_extractor.extract(html_content, url)
            
            if not extracted.get('raw_text') or len(extracted['raw_text']) < 100:
                self.stats.pages_skipped += 1
                self.stats.skipped_urls.append({"url": url, "reason": "Empty or insufficient content"})
                return False
            
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
            
            # Extract and queue new links
            links = self._extract_links(html_content, url)
            for link in links:
                if self._should_crawl_url(link):
                    self._add_url_to_visit(link, depth + 1)
            
            return True
            
        except Exception as e:
            logger.warning(f"Error processing {url}: {e}")
            self.stats.failed_urls.append({
                "url": url,
                "reason": str(e)[:200]
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
    
    def _extract_links(self, html_content: str, current_url: str) -> Set[str]:
        """Extract internal links from HTML."""
        links = set()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for anchor in soup.find_all('a', href=True):
                href = anchor.get('href', '').strip()
                
                if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                    continue
                
                absolute_url = urljoin(current_url, href)
                normalized = self._normalize_url(absolute_url)
                
                # Check if internal
                parsed = urlparse(normalized)
                if parsed.netloc == self.parsed_url.netloc:
                    links.add(normalized)
                    
        except Exception as e:
            logger.debug(f"Error extracting links: {e}")
        
        return links
    
    def _increase_delay(self):
        """Increase delay due to errors (backpressure)."""
        if self.consecutive_errors >= 3:
            self.current_delay = min(
                self.current_delay * 1.5,
                self.config.max_delay_seconds * 2
            )
            logger.info(f"Increased delay to {self.current_delay:.1f}s due to errors")
    
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
