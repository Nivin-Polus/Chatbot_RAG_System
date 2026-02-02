# app/services/crawler/__init__.py
"""
Smart Web Crawler Service
Production-ready web crawler with RAG optimization.
"""

from .config import CrawlConfig, CrawlStats, USER_AGENTS
from .content_extractor import ContentExtractor, SemanticBlock
from .chunker import TextChunker, ContentChunk
from .duplicate_detector import DuplicateDetector
from .sitemap_parser import SitemapParser
from .crawler_engine import CrawlerEngine
from .html_fetcher import fetch_static, is_empty_static, fetch_js_rendered, fetch_html, close_playwright

__all__ = [
    "CrawlConfig",
    "CrawlStats",
    "USER_AGENTS",
    "ContentExtractor",
    "SemanticBlock",
    "TextChunker",
    "ContentChunk",
    "DuplicateDetector",
    "SitemapParser",
    "CrawlerEngine",
    "fetch_static",
    "is_empty_static",
    "fetch_js_rendered",
    "fetch_html",
    "close_playwright",
]

