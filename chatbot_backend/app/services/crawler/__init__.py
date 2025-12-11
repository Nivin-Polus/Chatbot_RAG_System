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
    "CrawlerEngine"
]
