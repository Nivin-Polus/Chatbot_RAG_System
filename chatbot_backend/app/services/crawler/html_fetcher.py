# app/services/crawler/html_fetcher.py
"""
Hybrid HTML Fetcher
Tries fast static fetch first, falls back to Playwright for JavaScript-rendered pages.
Supports React, Angular, Vue, Next.js, Vite, and other SPA frameworks.

Enhanced for MIT Policy sites and similar content-heavy SPAs.
"""

import re
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger("html_fetcher")

# Modern User-Agent for requests
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# SPA framework markers (lowercase)
SPA_MARKERS = [
    '<div id="root"',      # React (Create React App)
    '<div id="__next"',    # Next.js
    '<div id="app"',       # Vue.js / Vite
    '<app-root',           # Angular
    'ng-version',          # Angular
    'data-reactroot',      # React
    '__nuxt',              # Nuxt.js
    'data-v-',             # Vue.js scoped styles
    '_next/static',        # Next.js static assets
    'vite',                # Vite bundler
]


class PlaywrightManager:
    """
    Singleton manager for Playwright browser context reuse.
    Opens browser once and reuses context for all JS-rendered pages.
    """
    _instance = None
    _browser = None
    _context = None
    _playwright = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_context(self):
        """Get or create a reusable browser context."""
        if self._context is None:
            self._start_browser()
        return self._context
    
    def _start_browser(self):
        """Start browser and create context."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self._context = self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=DEFAULT_USER_AGENT,
                ignore_https_errors=True
            )
            logger.info("🌐 Playwright browser started (context reuse enabled)")
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install chromium")
            raise
        except Exception as e:
            logger.error(f"Failed to start Playwright browser: {e}")
            raise
    
    def close(self):
        """Close browser and cleanup."""
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.info("🌐 Playwright browser closed")
    
    def __del__(self):
        self.close()


# Global manager instance
_playwright_manager: Optional[PlaywrightManager] = None


def get_playwright_manager() -> PlaywrightManager:
    """Get the global Playwright manager instance."""
    global _playwright_manager
    if _playwright_manager is None:
        _playwright_manager = PlaywrightManager()
    return _playwright_manager


def close_playwright():
    """Close the global Playwright browser (call when crawl is complete)."""
    global _playwright_manager
    if _playwright_manager:
        _playwright_manager.close()
        _playwright_manager = None


def fetch_static(url: str, timeout: int = 10) -> str:
    """
    Fast static HTML fetch using requests.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        HTML content as string, or empty string on failure
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            allow_redirects=True
        )
        if response.status_code != 200:
            logger.debug(f"Static fetch failed for {url}: HTTP {response.status_code}")
            return ""
        logger.debug(f"📄 Static fetch success: {url} ({len(response.text)} chars)")
        return response.text
    except requests.Timeout:
        logger.warning(f"⏱️ Static fetch timeout for {url}")
        return ""
    except requests.RequestException as e:
        logger.warning(f"🔴 Static fetch error for {url}: {e}")
        return ""
    except Exception as e:
        logger.debug(f"Unexpected error in static fetch for {url}: {e}")
        return ""


def is_empty_static(html: str) -> Tuple[bool, str]:
    """
    Detect if static HTML is empty or SPA-only (requires JS rendering).
    
    Args:
        html: Raw HTML content
        
    Returns:
        Tuple of (is_empty: bool, reason: str)
    """
    if not html:
        return True, "No HTML content"
    
    # Very short HTML is likely incomplete
    if len(html) < 5000:
        return True, f"HTML too short ({len(html)} chars)"
    
    # Check for SPA framework markers
    lower_html = html.lower()
    for marker in SPA_MARKERS:
        if marker in lower_html:
            return True, f"SPA marker detected: {marker}"
    
    # Extract visible text (text between > and <)
    text_matches = re.findall(r">([^<]+)<", html)
    visible_text = " ".join(text_matches).strip()
    
    # If very little visible text, likely SPA or empty page
    if len(visible_text) < 100:
        return True, f"Visible text too short ({len(visible_text)} chars)"
    
    return False, "Static HTML sufficient"


def fetch_js_rendered(url: str, timeout_ms: int = 30000, use_context_reuse: bool = True) -> str:
    """
    Fetch HTML using Playwright with JavaScript rendering.
    
    Features:
    - Waits for <main> element if present (for content-heavy sites)
    - Falls back to body if no main element
    - Browser context reuse for efficiency
    - Enhanced timeout handling
    
    Args:
        url: URL to fetch
        timeout_ms: Navigation timeout in milliseconds
        use_context_reuse: If True, reuse browser context
        
    Returns:
        Rendered HTML content as string
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        logger.error("Playwright not installed. Install with: pip install playwright && playwright install chromium")
        return ""
    
    page = None
    should_close_browser = False
    
    try:
        if use_context_reuse:
            # Use reusable browser context
            manager = get_playwright_manager()
            context = manager.get_context()
            page = context.new_page()
        else:
            # One-off browser instance
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=DEFAULT_USER_AGENT,
                ignore_https_errors=True
            )
            page = context.new_page()
            should_close_browser = True
        
        # Navigate to URL
        logger.debug(f"🌐 JS rendering: {url}")
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        
        # Check for HTTP errors
        if response and response.status >= 400:
            logger.warning(f"🔴 JS render HTTP error {response.status} for {url}")
            return ""
        
        # ============================================================
        # SPA HYDRATION WAIT SEQUENCE
        # Critical for React, Angular, Vue, Next.js and other JS apps
        # ============================================================
        
        # 1. Wait for network to become idle (SPA hydration typically involves XHR/fetch)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
            logger.debug(f"✅ Network idle for {url}")
        except PlaywrightTimeout:
            logger.debug(f"⚠️ Network did not become idle for {url}, continuing...")
        
        # 2. Wait for main content container (Next.js/React typically render into <main>)
        try:
            page.wait_for_selector("main", timeout=8000)
            logger.debug(f"✅ Found <main> element for {url}")
        except PlaywrightTimeout:
            # Fallback: wait for body with content
            try:
                page.wait_for_selector("body", timeout=3000)
                logger.debug(f"⚠️ No <main> found, using <body> for {url}")
            except PlaywrightTimeout:
                logger.warning(f"⏱️ Timeout waiting for body element on {url}")
        
        # 3. Ensure DOM has stable, rendered href links (catches lazy-loaded navs)
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('a[href]').length > 5",
                timeout=5000
            )
            logger.debug(f"✅ Stable links detected for {url}")
        except PlaywrightTimeout:
            logger.debug(f"⚠️ Could not verify stable links for {url}")
        
        # 4. Additional wait for any final JS execution
        page.wait_for_timeout(800)
        
        # Get final rendered HTML
        html = page.content()
        logger.info(f"✅ JS render complete: {url} ({len(html)} chars)")
        
        return html
        
    except PlaywrightTimeout as e:
        logger.warning(f"⏱️ JS render timeout for {url}: {e}")
        return ""
    except Exception as e:
        logger.error(f"🔴 JS render failed for {url}: {e}")
        return ""
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass
        if should_close_browser:
            try:
                context.close()
                browser.close()
                playwright.stop()
            except Exception:
                pass


def fetch_html(url: str) -> str:
    """
    Hybrid HTML fetch - tries static first, falls back to JS rendering.
    
    This is the main entry point for fetching HTML content.
    It optimizes for speed by trying static fetch first, only using
    Playwright when the page appears to be a SPA or empty.
    
    Args:
        url: URL to fetch
        
    Returns:
        HTML content as string
    """
    # Validate URL
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.warning(f"🔴 Invalid URL: {url}")
            return ""
    except Exception:
        logger.warning(f"🔴 URL parse error: {url}")
        return ""
    
    # Try static fetch first (fast)
    static_html = fetch_static(url)
    
    # Check if static HTML is sufficient
    is_empty, reason = is_empty_static(static_html)
    
    if not is_empty:
        logger.debug(f"📄 Using static HTML for: {url}")
        return static_html
    
    # Need JS rendering
    logger.info(f"⚠️ Static HTML insufficient ({reason}) → Using JS rendering for: {url}")
    return fetch_js_rendered(url)


# Async version for integration with existing async crawler
async def fetch_html_async(url: str) -> str:
    """
    Async hybrid HTML fetch - tries static first, falls back to JS rendering.
    
    Note: This runs the sync Playwright in a thread pool to avoid blocking.
    For high-volume crawling, the existing Playwright integration in
    crawler_engine.py may be more efficient.
    
    Args:
        url: URL to fetch
        
    Returns:
        HTML content as string
    """
    import asyncio
    
    # Static fetch can be done in a thread pool
    loop = asyncio.get_event_loop()
    static_html = await loop.run_in_executor(None, fetch_static, url)
    
    is_empty, reason = is_empty_static(static_html)
    
    if not is_empty:
        logger.debug(f"📄 Using static HTML for: {url}")
        return static_html
    
    # Need JS rendering - run in thread pool since sync_playwright blocks
    logger.info(f"⚠️ Static HTML insufficient ({reason}) → Using JS rendering for: {url}")
    return await loop.run_in_executor(None, fetch_js_rendered, url)
