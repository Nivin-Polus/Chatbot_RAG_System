# app/services/crawler/__init__.py
"""
Smart Web Crawler Service
Production-ready web crawler with RAG optimization.
"""

from .config import CrawlConfig, CrawlStats, USER_AGENTS
from .content_extractor import (
    ContentExtractor, 
    SemanticBlock, 
    StructuredSection,
    TemplateRegistry,
    reset_template_registry,
    get_template_registry
)
from .chunker import TextChunker, ContentChunk, SemanticChunker, EnhancedContentChunk
from .duplicate_detector import DuplicateDetector
from .sitemap_parser import SitemapParser
from .crawler_engine import CrawlerEngine
from .html_fetcher import fetch_static, is_empty_static, fetch_js_rendered, fetch_html, close_playwright
from .structured_data_extractor import StructuredDataExtractor
from .person_extractor import PersonExtractor

__all__ = [
    "CrawlConfig",
    "CrawlStats",
    "USER_AGENTS",
    "ContentExtractor",
    "SemanticBlock",
    "StructuredSection",
    "TemplateRegistry",
    "reset_template_registry",
    "get_template_registry",
    "TextChunker",
    "ContentChunk",
    "SemanticChunker",
    "EnhancedContentChunk",
    "DuplicateDetector",
    "SitemapParser",
    "CrawlerEngine",
    "fetch_static",
    "is_empty_static",
    "fetch_js_rendered",
    "fetch_html",
    "close_playwright",
    "StructuredDataExtractor",
    "PersonExtractor",
]

