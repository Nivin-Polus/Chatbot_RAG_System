# app/services/crawler/sitemap_parser.py
"""
Sitemap Parser
Automatically discovers and parses XML sitemaps for efficient crawling.
"""

import re
import logging
from typing import List, Set, Dict, Optional
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from datetime import datetime
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger("sitemap_parser")


@dataclass
class SitemapURL:
    """A URL entry from a sitemap."""
    
    loc: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "loc": self.loc,
            "lastmod": self.lastmod.isoformat() if self.lastmod else None,
            "changefreq": self.changefreq,
            "priority": self.priority
        }


class SitemapParser:
    """
    Parses XML sitemaps for URL discovery.
    
    Supports:
    - Standard sitemaps (sitemap.xml)
    - Sitemap indexes
    - robots.txt sitemap references
    - Compressed sitemaps (.gz)
    """
    
    # XML namespaces
    SITEMAP_NS = {
        '': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'xhtml': 'http://www.w3.org/1999/xhtml'
    }
    
    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize sitemap parser.
        
        Args:
            base_url: The base URL of the website
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.parsed = urlparse(base_url)
        self.domain = f"{self.parsed.scheme}://{self.parsed.netloc}"
        
        # Discovered URLs
        self.urls: List[SitemapURL] = []
        self.sitemap_urls: Set[str] = set()
    
    def discover_and_parse(self) -> List[SitemapURL]:
        """
        Discover and parse all sitemaps for the domain.
        
        Returns:
            List of SitemapURL objects
        """
        self.urls = []
        self.sitemap_urls = set()
        
        # 1. Check robots.txt for sitemap references
        sitemap_locations = self._get_sitemaps_from_robots()
        
        # 2. Add common sitemap locations
        common_locations = [
            f"{self.domain}/sitemap.xml",
            f"{self.domain}/sitemap_index.xml",
            f"{self.domain}/sitemap/sitemap.xml",
            f"{self.domain}/sitemaps.xml",
        ]
        
        for loc in common_locations:
            if loc not in sitemap_locations:
                sitemap_locations.append(loc)
        
        # 3. Parse each sitemap
        for sitemap_url in sitemap_locations:
            if sitemap_url not in self.sitemap_urls:
                self._parse_sitemap(sitemap_url)
        
        logger.info(f"Discovered {len(self.urls)} URLs from sitemaps")
        return self.urls
    
    def _get_sitemaps_from_robots(self) -> List[str]:
        """Extract sitemap URLs from robots.txt."""
        sitemaps = []
        robots_url = f"{self.domain}/robots.txt"
        
        try:
            response = requests.get(
                robots_url,
                timeout=self.timeout,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; WebCrawler/1.0)'}
            )
            
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    line = line.strip()
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        if sitemap_url:
                            sitemaps.append(sitemap_url)
                            logger.info(f"Found sitemap in robots.txt: {sitemap_url}")
        
        except Exception as e:
            logger.debug(f"Could not fetch robots.txt: {e}")
        
        return sitemaps
    
    def _parse_sitemap(self, url: str, depth: int = 0):
        """
        Parse a sitemap or sitemap index.
        
        Args:
            url: Sitemap URL
            depth: Recursion depth (to prevent infinite loops)
        """
        if depth > 5 or url in self.sitemap_urls:
            return
        
        self.sitemap_urls.add(url)
        
        try:
            # Fetch sitemap
            response = requests.get(
                url,
                timeout=self.timeout,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; WebCrawler/1.0)'}
            )
            
            if response.status_code != 200:
                logger.debug(f"Sitemap not found: {url} (status {response.status_code})")
                return
            
            content = response.text
            
            # Handle compressed sitemaps
            if url.endswith('.gz'):
                import gzip
                content = gzip.decompress(response.content).decode('utf-8')
            
            # Parse XML
            root = ET.fromstring(content)
            
            # Remove namespace prefixes for easier parsing
            tag_name = root.tag.split('}')[-1].lower()
            
            if tag_name == 'sitemapindex':
                # This is a sitemap index, parse child sitemaps
                self._parse_sitemap_index(root, depth)
            elif tag_name == 'urlset':
                # This is a regular sitemap
                self._parse_urlset(root)
            else:
                logger.warning(f"Unknown sitemap format at {url}: {tag_name}")
        
        except ET.ParseError as e:
            logger.debug(f"XML parse error for {url}: {e}")
        except Exception as e:
            logger.debug(f"Error parsing sitemap {url}: {e}")
    
    def _parse_sitemap_index(self, root: ET.Element, depth: int):
        """Parse a sitemap index and recurse into child sitemaps."""
        for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
            loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc is not None and loc.text:
                self._parse_sitemap(loc.text.strip(), depth + 1)
        
        # Also try without namespace
        for sitemap in root.findall('.//sitemap'):
            loc = sitemap.find('loc')
            if loc is not None and loc.text:
                self._parse_sitemap(loc.text.strip(), depth + 1)
    
    def _parse_urlset(self, root: ET.Element):
        """Parse URL entries from a sitemap."""
        # Try with namespace
        url_elements = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url')
        
        # Fallback without namespace
        if not url_elements:
            url_elements = root.findall('.//url')
        
        for url_elem in url_elements:
            url_entry = self._parse_url_entry(url_elem)
            if url_entry:
                self.urls.append(url_entry)
    
    def _parse_url_entry(self, url_elem: ET.Element) -> Optional[SitemapURL]:
        """Parse a single URL entry."""
        # Try with namespace
        loc = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc is None:
            loc = url_elem.find('loc')
        
        if loc is None or not loc.text:
            return None
        
        url = loc.text.strip()
        
        # Validate URL is on the same domain
        parsed = urlparse(url)
        if parsed.netloc and parsed.netloc != self.parsed.netloc:
            return None
        
        # Parse optional fields
        lastmod = None
        lastmod_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
        if lastmod_elem is None:
            lastmod_elem = url_elem.find('lastmod')
        if lastmod_elem is not None and lastmod_elem.text:
            lastmod = self._parse_date(lastmod_elem.text.strip())
        
        changefreq = None
        changefreq_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}changefreq')
        if changefreq_elem is None:
            changefreq_elem = url_elem.find('changefreq')
        if changefreq_elem is not None and changefreq_elem.text:
            changefreq = changefreq_elem.text.strip()
        
        priority = None
        priority_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}priority')
        if priority_elem is None:
            priority_elem = url_elem.find('priority')
        if priority_elem is not None and priority_elem.text:
            try:
                priority = float(priority_elem.text.strip())
            except ValueError:
                pass
        
        return SitemapURL(
            loc=url,
            lastmod=lastmod,
            changefreq=changefreq,
            priority=priority
        )
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse ISO 8601 date string."""
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m"
        ]
        
        # Handle timezone suffix variations
        date_str = re.sub(r'Z$', '+00:00', date_str)
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str[:len(fmt) + 6], fmt)
            except ValueError:
                continue
        
        return None
    
    def get_prioritized_urls(self, limit: int = 100) -> List[str]:
        """
        Get URLs sorted by priority.
        
        Args:
            limit: Maximum number of URLs to return
            
        Returns:
            List of URL strings
        """
        # Sort by priority (descending) and recency
        sorted_urls = sorted(
            self.urls,
            key=lambda u: (
                u.priority or 0.5,
                u.lastmod or datetime.min
            ),
            reverse=True
        )
        
        return [u.loc for u in sorted_urls[:limit]]
    
    def get_urls_since(self, since: datetime) -> List[str]:
        """
        Get URLs modified since a given date.
        
        Args:
            since: Only return URLs modified after this date
            
        Returns:
            List of URL strings
        """
        return [
            u.loc for u in self.urls
            if u.lastmod and u.lastmod > since
        ]
