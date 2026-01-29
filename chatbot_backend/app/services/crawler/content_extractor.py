# app/services/crawler/content_extractor.py
"""
Semantic Content Extractor - Phase 1 Enhanced
Extracts structured content from HTML with advanced quality scoring and boilerplate detection.

Features:
- DOM-based main content detection with scoring algorithm
- Enhanced boilerplate removal (nav, ads, cookies, social, etc.)
- Text cleaning and normalization
- Content quality validation and scoring
- Template/repeated content detection across pages
- Structure-preserving section extraction with heading hierarchy
- Page type detection with confidence scoring
- Structured data extraction (JSON-LD, Microdata, OpenGraph)
- Person/team member extraction
"""

import re
import hashlib
import unicodedata
import html
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Set, TYPE_CHECKING
from collections import defaultdict
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag, NavigableString
import logging

# Import structured data and person extractors
from .structured_data_extractor import StructuredDataExtractor
from .person_extractor import PersonExtractor

logger = logging.getLogger("content_extractor")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SemanticBlock:
    """A semantic block of content with metadata."""
    
    block_type: str  # header, paragraph, list, table, faq, code, quote
    content: str
    header: Optional[str] = None
    header_level: int = 0
    parent_headers: List[str] = field(default_factory=list)
    word_count: int = 0
    
    def __post_init__(self):
        self.word_count = len(self.content.split())
    
    def to_dict(self) -> dict:
        return {
            "block_type": self.block_type,
            "content": self.content,
            "header": self.header,
            "header_level": self.header_level,
            "parent_headers": self.parent_headers,
            "word_count": self.word_count
        }


@dataclass
class StructuredSection:
    """
    A structured section with full metadata for Phase 1 output contract.
    
    Represents content under a heading with quality scoring and structure detection.
    """
    
    text: str
    heading: Optional[str] = None
    heading_level: int = 0
    section_path: str = ""
    has_code: bool = False
    has_list: bool = False
    has_table: bool = False
    content_quality_score: float = 0.0
    is_boilerplate: bool = False
    word_count: int = 0
    domain: str = "general" # P1 FIX: Added domain tag
    metadata: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        self.word_count = len(self.text.split()) if self.text else 0
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API output."""
        return {
            "text": self.text,
            "heading": self.heading,
            "heading_level": self.heading_level,
            "section_path": self.section_path,
            "has_code": self.has_code,
            "has_list": self.has_list,
            "has_table": self.has_table,
            "content_quality_score": self.content_quality_score,
            "is_boilerplate": self.is_boilerplate,
            "word_count": self.word_count,
            "domain": self.domain, # P1 FIX
            "metadata": self.metadata or {}
        }


# =============================================================================
# TEMPLATE DETECTION REGISTRY (Module-level for cross-page tracking)
# =============================================================================

class TemplateRegistry:
    """
    Tracks section hashes across a crawl job for template detection.
    
    Sections appearing in >80% of pages are considered template/boilerplate.
    """
    
    def __init__(self):
        self._section_hashes: Dict[str, int] = defaultdict(int)  # hash -> count
        self._total_pages: int = 0
        self._threshold: float = 0.80  # 80% threshold
    
    def register_page(self):
        """Register that a new page has been processed."""
        self._total_pages += 1
    
    def register_section(self, text: str) -> str:
        """
        Register a section and return its hash.
        
        Args:
            text: Section text content
            
        Returns:
            SHA256 hash of normalized text
        """
        # Normalize text for consistent hashing
        normalized = self._normalize_for_hash(text)
        section_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
        self._section_hashes[section_hash] += 1
        return section_hash
    
    def is_template(self, text: str) -> bool:
        """
        Check if a section is template content (appears in >80% of pages).
        
        Args:
            text: Section text to check
            
        Returns:
            True if section is template/boilerplate
        """
        if self._total_pages < 5:
            # Need at least 5 pages to make template detection meaningful
            return False
        
        normalized = self._normalize_for_hash(text)
        section_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
        count = self._section_hashes.get(section_hash, 0)
        
        frequency = count / self._total_pages
        return frequency > self._threshold
    
    def _normalize_for_hash(self, text: str) -> str:
        """Normalize text for consistent hashing across pages."""
        # Lowercase, collapse whitespace, remove punctuation
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip()
    
    def reset(self):
        """Reset the registry for a new crawl job."""
        self._section_hashes.clear()
        self._total_pages = 0
    
    def get_stats(self) -> Dict:
        """Get template detection statistics."""
        return {
            "total_pages": self._total_pages,
            "unique_sections": len(self._section_hashes),
            "threshold": self._threshold
        }


# Global template registry - shared across ContentExtractor instances within a crawl
_template_registry = TemplateRegistry()


def reset_template_registry():
    """Reset the global template registry. Call at start of new crawl job."""
    global _template_registry
    _template_registry.reset()


def get_template_registry() -> TemplateRegistry:
    """Get the global template registry."""
    return _template_registry


# =============================================================================
# CONTENT EXTRACTOR
# =============================================================================

class ContentExtractor:
    """
    Extracts clean, structured content from HTML.
    
    Phase 1 Enhanced Features:
    - DOM-based main content detection with scoring
    - Advanced boilerplate removal
    - Text cleaning and normalization
    - Content quality validation and scoring
    - Template detection across pages
    - Structure-preserving section extraction
    """
    
    # -------------------------------------------------------------------------
    # CLASS CONSTANTS
    # -------------------------------------------------------------------------
    
    # Elements to remove completely
    REMOVE_TAGS = [
        'script', 'style', 'noscript', 'meta', 'link', 'head',
        'nav', 'footer', 'aside', 'header', 'form', 'button',
        'iframe', 'embed', 'object', 'svg', 'canvas'
    ]
    
    # Boilerplate class/ID patterns with word boundaries
    # Matches: nav, menu, sidebar, footer, cookie, consent, breadcrumb, ads, promo, banner, social
    BOILERPLATE_PATTERNS = [
        r'\bnav\b', r'\bnavigation\b', r'\bnavbar\b', r'\bmenu\b', r'\bmain-menu\b',
        r'\bsidebar\b', r'\bside-bar\b', r'\bleft-sidebar\b', r'\bright-sidebar\b',
        r'\bsite-header\b', r'\bsite-footer\b', r'\bpage-footer\b', r'\bfooter\b',
        r'\bcookie\b', r'\bcookie-banner\b', r'\bcookie-consent\b', r'\bgdpr\b',
        r'\bconsent\b', r'\bprivacy-notice\b',
        r'\bbreadcrumb\b', r'\bbreadcrumbs\b',
        r'\bads\b', r'\bad\b', r'\badvertisement\b', r'\bad-container\b', r'\bsponsored\b',
        r'\bpromo\b', r'\bpromotion\b', r'\bbanner\b',
        r'\bsocial\b', r'\bsocial-share\b', r'\bshare-buttons\b', r'\bsocial-media\b',
        r'\bskip-link\b', r'\bskip-to-content\b',
        r'\bpopup\b', r'\bmodal\b', r'\boverlay\b', r'\bdialog\b',
        r'\btoolbar\b', r'\bpagination\b',
        r'\bcomment\b', r'\bcomments\b', r'\bdisqus\b',
        r'\brelated-posts\b', r'\bsuggested\b', r'\brecommended\b',
        r'\bnewsletter\b', r'\bsubscribe\b', r'\bsubscription\b',
        r'\bsearch-form\b', r'\bsearch-box\b',
    ]
    
    # Elements that should NEVER be removed regardless of class/ID
    PROTECTED_TAGS = {'body', 'html', 'main', 'article'}
    
    # CSS code patterns for detection
    CSS_PATTERNS = [
        r'^[\.#@][\w\-]+[:\s\{]',
        r'[\w\-]+\s*:\s*[0-9]',
        r'\{[^}]{0,100}\}',
        r'px\s*;|em\s*;|rem\s*;|%\s*;',
    ]
    
    # JS code patterns for detection
    JS_PATTERNS = [
        r'^var\s+|^function\s+|^const\s+|^let\s+|^class\s+',
        r'=>|\(\)\s*=>|\bfunction\s*\(',
        r'document\.|window\.|console\.',
        r'\breturn\b.*;|\bif\s*\(|\bfor\s*\(|\bwhile\s*\(',
    ]
    
    # Quality thresholds
    MIN_SECTION_WORDS = 50
    MIN_ALPHANUMERIC_RATIO = 0.7
    MAX_LINK_DENSITY = 0.3
    MAX_SPECIAL_CHAR_RATIO = 0.2
    MIN_QUALITY_SCORE = 0.6
    
    # -------------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------------
    
    def __init__(self):
        """Initialize the ContentExtractor with compiled patterns."""
        self.boilerplate_pattern = re.compile(
            '|'.join(self.BOILERPLATE_PATTERNS),
            re.IGNORECASE
        )
        self._template_registry = get_template_registry()
        
        # Initialize Phase 1 extractors
        self._structured_data_extractor = StructuredDataExtractor()
        self._person_extractor = PersonExtractor()
        
        # Page type detection patterns
        self._team_url_patterns = [
            r'/team\b', r'/people\b', r'/leadership\b', r'/our-team\b',
            r'/staff\b', r'/about-us/team', r'/meet-the-team', r'/about/team',
            r'/executives\b', r'/management\b', r'/board\b'
        ]
        self._profile_url_patterns = [
            r'/team/[\w-]+$', r'/people/[\w-]+$', r'/about/[\w-]+$',
            r'/author/[\w-]+$', r'/speaker/[\w-]+$', r'/bio/[\w-]+$'
        ]
        self._blog_url_patterns = [
            r'/blog/', r'/posts/', r'/article/', r'/news/',
            r'/insights/', r'/resources/'
        ]
        self._product_url_patterns = [
            r'/product/', r'/products/', r'/shop/', r'/store/',
            r'/item/', r'/catalog/'
        ]

    
    # -------------------------------------------------------------------------
    # MAIN EXTRACTION METHOD
    # -------------------------------------------------------------------------
    
    def extract(self, html: str, url: str) -> Dict:
        """
        Extract structured content from HTML.
        
        Phase 1 Output Contract:
        {
            "url": "...",
            "title": "...",
            "canonical_url": "...",
            "meta_description": "...",
            "sections": [
                {
                    "text": "...",
                    "section_path": "Parent > Child > Current",
                    "heading_level": 2,
                    "content_quality_score": 0.85,
                    "is_boilerplate": false,
                    "has_code": false,
                    "has_list": true,
                    "has_table": false
                }
            ],
            "raw_text": "...",  # Backward compatibility
            "word_count": 1234
        }
        
        Only sections with content_quality_score >= 0.6 are included.
        
        Args:
            html: Raw HTML content
            url: Page URL
            
        Returns:
            Dict with extracted content and metadata
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Register page for template detection
            self._template_registry.register_page()
            
            # Extract metadata before modifying DOM
            title = self._extract_title(soup)
            meta_description = self._extract_meta_description(soup)
            canonical_url = self._extract_canonical(soup, url)
            
            # Phase 1: Extract structured data (JSON-LD, Microdata, OpenGraph)
            structured_data = self._structured_data_extractor.extract(soup, url)
            
            # Phase 1: Detect page type with confidence
            page_type = self.detect_page_type(soup, url, structured_data)
            
            # P3 FIX: Gate people extraction by domain
            page_domain = self._infer_page_domain(url, title)
            
            # Phase 1: Extract people/team members (Dual Path - Fix 3)
            # Path 1: Raw DOM (before cleaning)
            people_raw = []
            if page_domain not in ["admin", "policy", "research"]:
                people_raw = self._person_extractor.extract_people(soup, url, structured_data)
            else:
                 logger.debug(f"Skipping person extraction (raw) for {page_domain} page: {url}")
            
            # Determine Organizational Context (Fix 8)
            path_lower = url.lower()
            is_internal_page = any(kw in path_lower for kw in ['/about', '/team', '/leadership', '/who-we-are', '/management'])
            
            # Phase 1: Enhanced main content detection
            main_content = self.find_main_content_container(soup)
            
            if main_content is None:
                main_content = soup.find('body') or soup
            
            # Fix 6.2: Extract Elementor Cards 
            elementor_sections = self._extract_elementor_cards(main_content, is_internal_page)

             # Fix 7: Semantic Insurance (Universal Person Extraction)
            semantic_cards = self._extract_semantic_person_cards(main_content, is_internal_page)
            
            # Phase 1: Enhanced boilerplate removal (in-place)
            self.remove_boilerplate_elements(main_content)
            
            # Path 2: Cleaned DOM (after cleaning)
            people_clean = []
            if page_domain not in ["admin", "policy", "research"]:
                people_clean = self._person_extractor.extract_people(main_content, url, structured_data)
            
            # Merge and deduplicate
            # We trust cleaned extraction slightly more for precision, but raw for recall
            people_map = {p['name']: p for p in people_raw}
            for p in people_clean:
                if p['name'] in people_map:
                    # Merge info if needed, or prefer clean
                    pass
                else:
                    people_map[p['name']] = p
            people = list(people_map.values())
            
            # Phase 1: Extract structured sections with quality scoring
            # P1 FIX: Pass page-level domain metadata (Inferred earlier now)
            structured_sections = self.extract_structured_sections(main_content, page_domain)
            
            # Merge Elementor sections (Fix 6)
            structured_sections.extend(elementor_sections)

            # Merge Semantic Cards (Fix 7)
            # Deduplicate against Elementor cards
            existing_names = {s.metadata.get('name') for s in elementor_sections if s.metadata.get('name')}
            for card in semantic_cards:
                if card.metadata.get('name') not in existing_names:
                    structured_sections.append(card)
                    existing_names.add(card.metadata.get('name'))
            
            # Filter sections by quality score
            # Note: Elementor sections have high score (0.95) so they will pass
            filtered_sections = [
                s for s in structured_sections
                if s.content_quality_score >= self.MIN_QUALITY_SCORE and not s.is_boilerplate
            ]
            
            # Build raw text for backward compatibility
            raw_text = self._build_raw_text_from_sections(filtered_sections)
            
            # Fallback: if raw_text is too short, try full body text
            if len(raw_text.strip()) < 20:
                fallback_text = soup.get_text(separator=' ', strip=True)
                if fallback_text and len(fallback_text.strip()) >= len(raw_text.strip()):
                    raw_text = self.clean_extracted_text(fallback_text)
            
            # Also extract legacy SemanticBlock format for backward compat with chunker
            legacy_sections = self._extract_semantic_blocks(main_content)
            
            return {
                "title": title,
                "url": url,
                "canonical_url": canonical_url,
                "meta_description": meta_description,
                # Phase 1: New structured data fields
                "page_type": page_type,
                "structured_data": structured_data,
                "people": people,
                # Phase 1 new format
                "sections": [s.to_dict() for s in filtered_sections],
                # Backward compatibility
                "legacy_sections": legacy_sections,  # List[SemanticBlock]
                "raw_text": raw_text,
                "word_count": len(raw_text.split())
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return {
                "title": "",
                "url": url,
                "canonical_url": url,
                "meta_description": "",
                "page_type": {"type": "general", "confidence": 0.0, "signals": []},
                "structured_data": None,
                "people": [],
                "sections": [],
                "legacy_sections": [],
                "raw_text": "",
                "word_count": 0,
                "error": str(e)
            }
    
    # -------------------------------------------------------------------------
    # PAGE TYPE DETECTION
    # -------------------------------------------------------------------------
    
    def detect_page_type(
        self, 
        soup: BeautifulSoup, 
        url: str, 
        structured_data: Optional[Dict]
    ) -> Dict:
        """
        Detect the type of page with confidence scoring.
        
        Returns:
            {
                "type": "team_page" | "person_profile" | "blog_post" | "product_page" | "general",
                "confidence": 0.0-1.0,
                "signals": ["signal1", "signal2", ...]
            }
        """
        signals = []
        scores = {
            "team_page": 0.0,
            "person_profile": 0.0,
            "blog_post": 0.0,
            "product_page": 0.0,
            "general": 0.1  # Base score for general
        }
        
        # URL-based detection
        url_lower = url.lower()
        
        # Team page URL patterns (weight: 0.25)
        for pattern in self._team_url_patterns:
            if re.search(pattern, url_lower):
                scores["team_page"] += 0.25
                signals.append("url_pattern_team")
                break
        
        # Profile page URL patterns (weight: 0.25)
        for pattern in self._profile_url_patterns:
            if re.search(pattern, url_lower):
                scores["person_profile"] += 0.25
                signals.append("url_pattern_profile")
                break
        
        # Blog URL patterns (weight: 0.25)
        for pattern in self._blog_url_patterns:
            if re.search(pattern, url_lower):
                scores["blog_post"] += 0.25
                signals.append("url_pattern_blog")
                break
        
        # Product URL patterns (weight: 0.25)
        for pattern in self._product_url_patterns:
            if re.search(pattern, url_lower):
                scores["product_page"] += 0.25
                signals.append("url_pattern_product")
                break
        
        # Structured data detection
        if structured_data:
            persons = structured_data.get("persons", [])
            
            # Multiple persons = team page (weight: 0.30)
            if len(persons) >= 3:
                scores["team_page"] += 0.30
                signals.append("multiple_person_schema")
            
            # Single person with detailed info = profile page (weight: 0.30)
            elif len(persons) == 1:
                person = persons[0]
                if person.get("description") and len(person.get("description", "")) > 100:
                    scores["person_profile"] += 0.30
                    signals.append("single_person_schema_with_bio")
                else:
                    scores["person_profile"] += 0.15
                    signals.append("single_person_schema")
            
            # Check for blog posting schema
            json_ld = structured_data.get("json_ld", [])
            for item in json_ld:
                data = item.get("data", {})
                item_type = data.get("@type", "")
                if isinstance(item_type, list):
                    item_type = item_type[0] if item_type else ""
                
                if item_type in ("BlogPosting", "Article", "NewsArticle"):
                    scores["blog_post"] += 0.30
                    signals.append("blog_posting_schema")
                    break
                elif item_type == "Product":
                    scores["product_page"] += 0.30
                    signals.append("product_schema")
                    break
        
        # Content-based detection
        
        # Check for team keywords in headings (weight: 0.20)
        team_keywords = ["team", "our people", "leadership", "staff", "meet the team", 
                         "our team", "management", "executives", "board"]
        for heading in soup.find_all(['h1', 'h2']):
            heading_text = heading.get_text(strip=True).lower()
            if any(kw in heading_text for kw in team_keywords):
                scores["team_page"] += 0.20
                signals.append("team_keywords_in_heading")
                break
        
        # Check for multiple person cards (weight: 0.25)
        person_card_patterns = [
            r'team[-_]?member', r'person[-_]?card', r'staff[-_]?member',
            r'employee', r'people[-_]?item', r'leader[-_]?card'
        ]
        person_card_pattern = re.compile('|'.join(person_card_patterns), re.IGNORECASE)
        
        card_count = 0
        for element in soup.find_all(True):
            classes = ' '.join(element.get('class', []))
            if person_card_pattern.search(classes):
                card_count += 1
        
        if card_count >= 3:
            scores["team_page"] += 0.25
            signals.append("multiple_person_cards")
        
        # Check for long bio content for profile pages (weight: 0.30)
        body_text = soup.get_text(strip=True)
        word_count = len(body_text.split())
        
        # Profile pages typically have 200+ word bio
        if word_count >= 200 and "url_pattern_profile" in signals:
            scores["person_profile"] += 0.30
            signals.append("long_bio_content")
        
        # Check for social links (indicator of profile page)
        social_link_count = 0
        for a in soup.find_all('a', href=True):
            href = a.get('href', '').lower()
            if any(social in href for social in ['linkedin.com', 'twitter.com', 'x.com', 'github.com']):
                social_link_count += 1
        
        if social_link_count >= 2 and scores["person_profile"] > 0:
            scores["person_profile"] += 0.10
            signals.append("social_links_present")
        
        # Determine best match
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Fallback to general if confidence is too low
        if best_score < 0.5:
            best_type = "general"
            best_score = scores["general"]
        
        # Remove duplicate signals
        signals = list(dict.fromkeys(signals))
        
        # --- PHASE 2: AI Classification (Refinement 3) ---
        # Only call if heuristic is not super confident (save costs) 
        # OR if it's a critical page (e.g. potential profile but unsure)
        # Note: leadership_classifier has its own cache so safe to call repeatedly for same URL
        
        from app.services.leadership_classifier import leadership_classifier
        
        if min(best_score, 1.0) < 0.85:
             try:
                 # Extract a snippet for classification (first 500 chars of body)
                 body_text = soup.body.get_text(strip=True)[:1000] if soup.body else ""
                 
                 ai_result = leadership_classifier.classify_page_type(url, body_text)
                 ai_type = ai_result.get("type")
                 ai_conf = ai_result.get("confidence", 0.0)
                 
                 if ai_conf > 0.6: # Trust AI if reasonably confident
                     best_type = ai_type
                     best_score = max(best_score, ai_conf)
                     signals.append(f"ai_classified_{ai_type}")
             except Exception as e:
                 logger.warning(f"AI page classification failed: {e}")
                 
        return {
            "type": best_type,
            "confidence": min(best_score, 1.0),  # Cap at 1.0
            "signals": signals
        }
    
    # -------------------------------------------------------------------------
    # 1. MAIN CONTENT DETECTION (DOM-based scoring)
    # -------------------------------------------------------------------------
    
    def find_main_content_container(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find the main content container using DOM-based scoring algorithm.
        
        Scoring formula:
            score = (text_length * 10) + (paragraph_count * 100) - (link_density * 200)
        
        Prefers <main> and <article> tags when scores are similar.
        Falls back to <body> if confidence is low.
        
        Args:
            soup: BeautifulSoup parsed HTML
            
        Returns:
            The main content container Tag, or None if not found
        """
        candidates = []
        
        # Collect candidate containers: main, article, section, div
        for tag_name in ['main', 'article', 'section', 'div']:
            for element in soup.find_all(tag_name):
                # Skip very small containers
                text = element.get_text(strip=True)
                if len(text) < 100:
                    continue
                
                # Calculate scoring components
                text_length = len(text)
                paragraph_count = len(element.find_all('p'))
                
                # Calculate link density: links / paragraphs
                link_count = len(element.find_all('a'))
                link_density = link_count / max(paragraph_count, 1)
                
                # Apply scoring formula
                score = (text_length * 10) + (paragraph_count * 100) - (link_density * 200)
                
                # Bonus for semantic tags
                if tag_name == 'main':
                    score += 500  # Strong preference for <main>
                elif tag_name == 'article':
                    score += 300  # Good preference for <article>
                
                # Bonus for role="main"
                if element.get('role') == 'main':
                    score += 400
                
                # Bonus for content-related IDs/classes
                element_id = (element.get('id') or '').lower()
                element_class = ' '.join(element.get('class', [])).lower()
                if any(kw in element_id or kw in element_class 
                       for kw in ['content', 'main', 'article', 'post', 'entry']):
                    score += 200
                
                # Penalty for boilerplate patterns in ID/class
                if self.boilerplate_pattern.search(element_id) or \
                   self.boilerplate_pattern.search(element_class):
                    score -= 500
                
                candidates.append((element, score, tag_name))
        
        if not candidates:
            logger.debug("No content candidates found, falling back to body")
            return None
        
        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        best_candidate, best_score, best_tag = candidates[0]
        
        # Confidence check: if best score is too low, fall back to body
        if best_score < 1000:
            logger.debug(f"Low confidence score ({best_score}), falling back to body")
            return None
        
        logger.debug(f"Selected main content: <{best_tag}> with score {best_score}")
        return best_candidate
    
    # -------------------------------------------------------------------------
    # 2. BOILERPLATE REMOVAL
    # -------------------------------------------------------------------------
    
    def remove_boilerplate_elements(self, container: Tag) -> None:
        """
        Remove navigation, ads, cookies, and other boilerplate content in-place.
        
        Removes:
        - Tags: nav, header, footer, aside, form
        - Elements with role="navigation"
        - Elements with class/id containing boilerplate keywords
        - Tags: script, style, iframe, svg
        
        Args:
            container: The content container to clean (modified in-place)
        """
        if container is None:
            return
        
        # Remove specific boilerplate tags
        boilerplate_tags = ['nav', 'footer', 'aside', 'header', 'form', 
                           'script', 'style', 'noscript', 'iframe', 'svg',
                           'canvas', 'embed', 'object']
        
        for tag_name in boilerplate_tags:
            for element in container.find_all(tag_name):
                try:
                    element.decompose()
                except Exception:
                    continue
        
        # Remove elements with boilerplate attributes
        for element in list(container.find_all(True)):
            try:
                # Never remove protected tags
                if element.name in self.PROTECTED_TAGS:
                    continue
                
                should_remove = False
                
                # Check role attribute
                role = element.get('role', '').lower()
                if role in ['navigation', 'banner', 'contentinfo', 'complementary', 'search']:
                    should_remove = True
                
                # Check class attribute
                class_attr = element.get('class', [])
                classes = ' '.join(class_attr) if class_attr else ''
                if self.boilerplate_pattern.search(classes):
                    should_remove = True
                
                # Check id attribute
                element_id = element.get('id', '') or ''
                if self.boilerplate_pattern.search(element_id):
                    should_remove = True
                
                # Check data attributes for common ad networks
                for attr_name, attr_value in element.attrs.items():
                    if isinstance(attr_value, str) and attr_name.startswith('data-'):
                        if any(kw in attr_value.lower() for kw in ['ad', 'cookie', 'consent', 'gdpr']):
                            should_remove = True
                            break
                
                # Fix 6.1: Elementor Protection
                if should_remove:
                    if self._is_semantic_container(element):
                        should_remove = False

                if should_remove:
                    element.decompose()
                    
            except Exception:
                # Skip elements that can't be processed
                continue

    def _is_semantic_container(self, element: Tag) -> bool:
        """
        Check if element is a semantic container that should be preserved.
        Fix 6.1: Elementor-aware protection.
        """
        # Check for Elementor heading widget
        if element.select_one(".elementor-widget-heading"):
            return True
        # Check for standard headings (h1-h6) as explicit children or descendants
        if element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            return True
        return False

    def _extract_elementor_cards(self, root: Tag, is_internal_page: bool = False) -> List[StructuredSection]:
        """
        Explicitly extract 'Person Cards' from Elementor structures.
        Fix 6.2 & 6.3.
        """
        cards = []
        if not root:
            return cards
            
        # Query for all Elementor containers and columns
        # .e-con is Flexbox container, .elementor-column is legacy column
        containers = root.select(".e-con, .elementor-column, .elementor-widget-wrap")
        
        # Track processed to avoid duplicates
        processed_keys = set()
        
        for container in containers:
            # Check for name (Heading)
            # Elementor headings usually use h1-h6 tags inside .elementor-widget-heading
            name_el = container.select_one(".elementor-widget-heading h1, .elementor-widget-heading h2, .elementor-widget-heading h3, .elementor-widget-heading h4, .elementor-widget-heading h5, .elementor-widget-heading h6")
            
            # Check for role (Text Editor) - usually a p tag inside .elementor-widget-text-editor
            # Sometimes just text inside div
            role_el = container.select_one(".elementor-widget-text-editor p, .elementor-widget-text-editor div, .elementor-widget-text-editor")
            
            if name_el:
                name = name_el.get_text(strip=True)
                title = role_el.get_text(strip=True) if role_el else ""
                
                # Check for LinkedIn (Social Icons) - Strong signal
                linkedin_el = container.select_one("a[href*='linkedin.com']")
                
                # Validation: Needs Name AND (Title OR LinkedIn)
                if not name or (not title and not linkedin_el):
                    continue
                
                
                # Basic validation: Name should be short, Title reasonable
                if len(name) > 60 or len(title) > 150:
                    continue
                
                # Ensure name looks like a name (at least 2 words)
                if len(name.split()) < 2:
                    continue
                
                # Deduplication key
                key = f"{name}:{title}"
                if key in processed_keys:
                    continue
                processed_keys.add(key)
                
                # Create section content
                card_text = f"{name}\n{title}"
                link = None
                if linkedin_el:
                    link = linkedin_el.get('href')
                    card_text += f"\nLinkedIn: {link}"
                
                # Context Analysis (Fix 8)
                org_context = "site_owner" if is_internal_page else "external"
                person_type = "internal" if is_internal_page else "external_reference"
                confidence_score = 1.0 # High confidence for Elementor cards
                
                # Semantic Guardrail: Check for testimonial keywords nearby
                # (Look at container text or parent headings)
                context_text = ""
                p = container.parent
                for _ in range(3):
                    if p:
                        context_text += " " + p.get_text(separator=' ', strip=True).lower()
                        p = p.parent
                    else: break
                
                testimonial_keywords = ["testimonial", "client", "partner", "customer", "case study", "what our clients say"]
                if any(kw in context_text for kw in testimonial_keywords):
                    org_context = "external"
                    person_type = "external_reference"
                    confidence_score = 0.3
                
                # Fix 6.3: Create person_profile DIRECTLY
                section = StructuredSection(
                    text=card_text,
                    heading=name,
                    heading_level=3, # Assume H3 level for cards context
                    section_path=f"Elementor Card > {name}",
                    content_quality_score=0.95, # High confidence
                    is_boilerplate=False,
                    metadata={
                        "doc_type": "person_profile",
                        "type": "person_profile", 
                        "name": name,
                        "title": title,
                        "linkedin": link,
                        "source": "elementor_card",
                        "confidence": "high",
                        "confidence_score": confidence_score,
                        "extraction_method": "elementor_card",
                        "organization_context": org_context,
                        "person_type": person_type
                    }
                )
                cards.append(section)
        
        if cards:
            logger.info(f"Extracted {len(cards)} Elementor person cards")
            
        return cards
    
    def _extract_semantic_person_cards(self, root: Tag, is_internal_page: bool = False) -> List[StructuredSection]:
        """
        Universal, CMS-agnostic extraction of "Person Cards".
        Algorithm:
        1. Traverse text nodes.
        2. Identify 'Name' candidate nodes.
        3. Search nearby siblings/cousins for 'Role' candidate nodes.
        4. Cluster them into a Person Card.
        """
        cards = []
        if not root:
            return cards
            
        # 1. Find all potential name text nodes
        # Use a generator to traverse
        candidates = []
        
        # Limit traversal to body or main containers to avoid header/footer noise if possible
        # But root should be passed correctly
        
        # We look for text nodes directly
        for element in root.find_all(text=True):
            text = element.strip()
            if not text:
                continue
                
            if self.is_person_name(text):
                parent = element.parent
                candidates.append((element, parent))
                
        # 2. Check for roles near names
        processed_parents = set()
        
        for text_node, parent in candidates:
            # Skip if we already processed this area
            if parent in processed_parents:
                continue
                
            name = text_node.strip()
            
            # Look for role in:
            # - Siblings
            # - Parent's siblings (Cousins)
            # - Parent's parent's siblings
            
            role = None
            role_node = None
            
            # Search Scope: Smart Lookahead
            # Search next elements (siblings/cousins/descendants in order)
            # Limit scope to Avoid crossing into next card
            
            # Look ahead up to 50 text nodes (covers complex cards)
            lookahead_nodes = list(text_node.find_all_next(string=True, limit=50))
            
            for node in lookahead_nodes:
                text = node.strip()
                if not text:
                    continue
                    
                # STOP Condition: Encounter another valid Person Name
                # This prevents pairing Name 1 with Role 2 in a grid
                if self.is_person_name(text):
                    break
                    
                # Match Condition: Found a Role
                if self.is_role_text(text):
                    role = text
                    role_node = node
                    break
            
            if role:
                # Found a pair!
                # Identify the common container
                common_container = parent
                # Walk up until we cover both or max 3 levels
                # Determine Identity Link
                
                # Check for LinkedIn
                linkedin_link = None
                
                # Heuristic: Find common parent of name and role
                # or just use name's parent parent
                card_wrapper = parent
                for _ in range(3):
                    if card_wrapper.parent and card_wrapper.parent.name != 'body':
                        card_wrapper = card_wrapper.parent
                        # If detecting next Person Name in this wrapper, maybe went too far?
                        # But we just look for linkedin link inside
                        l_link = card_wrapper.find('a', href=re.compile(r'linkedin\.com'))
                        if l_link:
                            linkedin_link = l_link['href']
                            break
                
                # Deduplicate
                dedup_key = f"{name}:{role}"
                
                # Create Section
                card_text = f"{name}\n{role}"
                if linkedin_link:
                    card_text += f"\nLinkedIn: {linkedin_link}"
                    
                # Context Analysis (Fix 8)
                org_context = "site_owner" if is_internal_page else "external"
                person_type = "internal" if is_internal_page else "external_reference"
                confidence_score = 0.90
                
                # Semantic Guardrail
                context_text = card_wrapper.get_text(separator=' ', strip=True).lower()
                testimonial_keywords = ["testimonial", "client", "partner", "customer", "case study", "what our clients say"]
                if any(kw in context_text for kw in testimonial_keywords):
                    org_context = "external"
                    person_type = "external_reference"
                    confidence_score = 0.3
                    
                section = StructuredSection(
                    text=card_text,
                    heading=name,
                    heading_level=3,
                    section_path=f"Semantic Card > {name}",
                    content_quality_score=0.90, # High confidence
                    is_boilerplate=False,
                    metadata={
                        "doc_type": "person_profile",
                        "type": "person_profile",
                        "name": name,
                        "title": role,
                        "linkedin": linkedin_link,
                        "source": "semantic_card",
                        "confidence": "high",
                        "confidence_score": confidence_score,
                        "extraction_method": "semantic_card",
                        "organization_context": org_context,
                        "person_type": person_type
                    }
                )
                
                cards.append(section)
                
                # Mark as processed to avoid double counting elements in this card
                processed_parents.add(parent)
                if role_node:
                    processed_parents.add(role_node.parent)
        
        if cards:
            logger.info(f"Extracted {len(cards)} Semantic Person Cards")
            
        return cards
    
    # -------------------------------------------------------------------------
    # 3. TEXT CLEANING
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # 3. TEXT CLEANING & SEMANTIC HELPERS
    # -------------------------------------------------------------------------

    def is_person_name(self, text: str) -> bool:
        """
        Check if text looks like a person's name (Universal, CMS-agnostic).
        Rules:
        - 2-4 words
        - Majority capitalized
        - No role keywords
        - Alpha only (plus -.')
        """
        if not text or len(text) > 50:
            return False
            
        words = text.strip().split()
        if not (2 <= len(words) <= 4):
            return False
            
        # Check capitalization (allow 1 lower case word like 'de', 'van')
        cap_count = sum(1 for w in words if w[0].isupper())
        if cap_count < len(words) - 1:
            return False
            
        # Check for role keywords (don't want "Executive Director" treated as a name)
        if self.is_role_text(text):
            return False
            
        # Check chars (mostly alpha)
        cleaned = re.sub(r'[ \-\.\']', '', text)
        return cleaned.isalpha()

    def is_role_text(self, text: str) -> bool:
        """
        Check if text looks like a job role/title.
        """
        if not text or len(text) > 100:
            return False
            
        text_lower = text.lower()
        
        # Robust keyword list
        keywords = [
            'ceo', 'cto', 'cfo', 'cmo', 'coo', 'cio', 'ciso', 'vp', 'svp', 'evp',
            'president', 'director', 'manager', 'head of', 'lead', 'chief',
            'founder', 'co-founder', 'owner', 'partner', 'principal',
            'engineer', 'developer', 'designer', 'architect', 'consultant',
            'specialist', 'strategist', 'analyst', 'administrator', 'coordinator',
            'officer', 'executive', 'chairman', 'chairwoman', 'chair',
            'board member', 'advisor', 'scientist', 'researcher',
            'associate', 'assistant', 'representative'
        ]
        
        # Strict match or word boundary match
        # (Avoid partial matches like "Place" containing "ace")
        for kw in keywords:
            # Check for exact phrase or bounded word
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                return True
                
        return False

    def contains_name_or_title(self, text: str) -> bool:
        """
        Check if text likely contains a person's name or job title.
        Legacy helper, preserved for short-block protection.
        """
        return self.is_person_name(text) or self.is_role_text(text)
    
    def clean_extracted_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.
        
        Operations:
        - Normalize whitespace (collapse multiple spaces/newlines)
        - Decode HTML entities
        - Remove JS/CSS artifacts
        - Normalize unicode (NFKC)
        - Remove repeated short lines (navigation remnants)
        - Remove lines shorter than 3 words (unless likely heading/code)
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""
        
        # Step 1: Decode HTML entities
        text = html.unescape(text)
        
        # Step 2: Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        
        # Step 3: Remove common JS/CSS artifacts
        # Remove inline JS patterns
        text = re.sub(r'function\s*\([^)]*\)\s*\{[^}]*\}', '', text)
        text = re.sub(r'var\s+\w+\s*=\s*[^;]+;', '', text)
        text = re.sub(r'\$\([^)]*\)\.[^;]+;', '', text)  # jQuery patterns
        
        # Remove CSS patterns
        text = re.sub(r'[\.#][\w-]+\s*\{[^}]*\}', '', text)
        text = re.sub(r'@media[^{]+\{[^}]*\}', '', text)
        
        # Remove data URIs
        text = re.sub(r'data:[a-zA-Z0-9+/=;,]+', '', text)
        
        # Step 4: Normalize whitespace
        # Replace tabs and form feeds with spaces
        text = re.sub(r'[\t\f\v]', ' ', text)
        # Collapse multiple spaces
        text = re.sub(r' +', ' ', text)
        # Normalize line endings
        text = re.sub(r'\r\n|\r', '\n', text)
        # Collapse multiple newlines to max 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Step 5: Process lines - remove navigation remnants
        lines = text.split('\n')
        cleaned_lines = []
        
        # Track to detect repeated patterns
        line_counter = defaultdict(int)
        for line in lines:
            stripped = line.strip()
            if stripped:
                line_counter[stripped] += 1
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                # Keep one empty line for paragraph separation
                if cleaned_lines and cleaned_lines[-1] != '':
                    cleaned_lines.append('')
                continue
            
            word_count = len(stripped.split())
            
            # Skip very short lines (navigation remnants)
            if word_count < 3:
                # Allow if it looks like a heading (ends with colon or is title case)
                is_heading_like = (
                    stripped.endswith(':') or
                    stripped.istitle() or
                    stripped.isupper()
                )
                # Allow if it's a list marker or number
                is_marker = bool(re.match(r'^[\d\-\•\*\→]+\.?\s*$', stripped))
                
                # FIX 1: Short-Block Protection
                # Allow if it likely contains a person name or title
                has_name_or_title = self.contains_name_or_title(stripped)
                
                if not is_heading_like and not is_marker and not has_name_or_title:
                    continue
            
            # Skip lines that appear too frequently (likely navigation)
            if line_counter[stripped] > 3 and word_count < 10:
                continue
            
            cleaned_lines.append(stripped)
        
        # Join and final cleanup
        result = '\n'.join(cleaned_lines)
        result = result.strip()
        
        return result
    
    # -------------------------------------------------------------------------
    # 4. CONTENT QUALITY VALIDATION
    # -------------------------------------------------------------------------
    
    def is_high_quality_section(self, text: str) -> bool:
        """
        Check if a text section meets quality thresholds.
        
        Rejection criteria:
        - Less than 50 words
        - Alphanumeric ratio < 0.7
        - Link density > 0.3 (estimated from URL patterns)
        - Special characters > 20%
        
        Args:
            text: Section text to validate
            
        Returns:
            True if section meets quality thresholds
        """
        if not text:
            return False
        
        # Word count check
        words = text.split()
        word_count = len(words)
        
        # Fix 1: Relax word count check if it looks like a person/title
        if word_count < self.MIN_SECTION_WORDS:
            if word_count >= 5 and self.contains_name_or_title(text):
                # Allow shorter sections if they contain important entity info
                pass 
            else:
                return False
        
        # Alphanumeric ratio check
        alphanumeric_chars = sum(1 for c in text if c.isalnum())
        total_chars = len(text)
        if total_chars > 0:
            alphanumeric_ratio = alphanumeric_chars / total_chars
            if alphanumeric_ratio < self.MIN_ALPHANUMERIC_RATIO:
                return False
        
        # Special character ratio check
        special_chars = sum(1 for c in text if c in '{}[]()<>;:@#$%^&*=+|\\~`')
        if total_chars > 0:
            special_ratio = special_chars / total_chars
            if special_ratio > self.MAX_SPECIAL_CHAR_RATIO:
                return False
        
        # Link density check (estimate from URL patterns in text)
        url_pattern = r'https?://[^\s]+'
        url_matches = re.findall(url_pattern, text)
        estimated_link_density = len(url_matches) / max(word_count, 1)
        if estimated_link_density > self.MAX_LINK_DENSITY:
            return False
        
        return True
    
    # -------------------------------------------------------------------------
    # 5. TEMPLATE DETECTION
    # -------------------------------------------------------------------------
    
    def _compute_section_hash(self, text: str) -> str:
        """
        Compute SHA256 hash of normalized section text.
        
        Args:
            text: Section text
            
        Returns:
            16-character hex hash
        """
        normalized = text.lower()
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return hashlib.sha256(normalized.strip().encode('utf-8')).hexdigest()[:16]
    
    def _is_template_content(self, text: str) -> bool:
        """
        Check if section is template content (appears in >80% of pages).
        
        Uses the global template registry for cross-page tracking.
        
        Args:
            text: Section text to check
            
        Returns:
            True if identified as template/boilerplate
        """
        return self._template_registry.is_template(text)
    
    # -------------------------------------------------------------------------
    # 6. STRUCTURE-PRESERVING SECTION EXTRACTION
    # -------------------------------------------------------------------------
    
    def extract_structured_sections(self, container: Tag, page_domain: str = "general") -> List[StructuredSection]:
        """
        Extract sections with heading hierarchy and structure metadata.
        
        Each section includes:
        - text: Section content
        - heading: Current heading text
        - heading_level: H1=1, H2=2, etc.
        - section_path: "Parent > Child > Current" hierarchy
        - has_code, has_list, has_table: Structure flags
        - content_quality_score: 0.0-1.0 quality rating
        - is_boilerplate: Template detection flag
        
        Rules:
        - Content belongs to nearest preceding heading
        - Stop section at next heading of same or higher level
        - Preserve lists, tables, code blocks intact
        
        Args:
            container: Content container to extract from
            page_domain: Domain tag inferred from page level (default for sections)
            
        Returns:
            List of StructuredSection objects
        """
        sections = []
        
        # Track heading stack for section_path
        heading_stack: List[Tuple[int, str]] = []  # (level, text)
        
        # Current section accumulator
        current_content: List[str] = []
        current_heading: Optional[str] = None
        current_level: int = 0
        current_has_code: bool = False
        current_has_list: bool = False
        current_has_table: bool = False
        
        def flush_section():
            """Flush accumulated content as a section."""
            nonlocal current_content, current_heading, current_level
            nonlocal current_has_code, current_has_list, current_has_table
            
            if not current_content:
                return
            
            # Join content
            text = '\n'.join(current_content)
            text = self.clean_extracted_text(text)
            
            if not text or len(text.strip()) < 20:
                current_content = []
                return
            
            # Build section path
            section_path = ' > '.join(h[1] for h in heading_stack)
            if current_heading and (not heading_stack or heading_stack[-1][1] != current_heading):
                if section_path:
                    section_path += f' > {current_heading}'
                else:
                    section_path = current_heading
            
            # Calculate quality score
            metadata = {
                'has_code': current_has_code,
                'has_list': current_has_list,
                'has_table': current_has_table,
                'heading': current_heading
            }
            quality_score = self.score_content_quality(text, metadata)
            
            # Check template detection
            self._template_registry.register_section(text)
            is_boilerplate = self._is_template_content(text)
            
            # Create section
            section = StructuredSection(
                text=text,
                heading=current_heading,
                heading_level=current_level,
                section_path=section_path,
                has_code=current_has_code,
                has_list=current_has_list,
                has_table=current_has_table,
                content_quality_score=quality_score,
                is_boilerplate=is_boilerplate,
                domain=page_domain # P1 FIX
            )
            sections.append(section)
            
            # Reset accumulators
            current_content = []
            current_has_code = False
            current_has_list = False
            current_has_table = False
        
        # Track processed elements to avoid duplication when handling nested cards
        processed_ids = set()

        # Iterate through all relevant elements, including article for cards
        for element in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                                           'p', 'ul', 'ol', 'table', 'pre', 
                                           'blockquote', 'div', 'code', 'article']):
            
            if id(element) in processed_ids:
                continue

            # FIX 2: Card-Based Section Detection
            # Check if this element is a "card" (person/team profile)
            if self._is_card_element(element):
                # Flush pending content
                flush_section()
                
                # Extract card content
                card_text = self._extract_card_text(element)
                if card_text:
                    # Mark children as processed
                    for child in element.find_all(True):
                        processed_ids.add(id(child))
                    
                    # Create a specific section for this card
                    self._template_registry.register_section(card_text)
                    
                    # Extract name/title for metadata if possible
                    name_title_meta = self._extract_card_metadata(element)
                    
                    section = StructuredSection(
                        text=card_text,
                        heading=current_heading,
                        heading_level=current_level + 1, # Treat as sub-item
                        section_path=f"{' > '.join(h[1] for h in heading_stack)} > {name_title_meta.get('name', 'Card')}",
                        content_quality_score=0.9, # High score for cards
                        is_boilerplate=False,
                        domain="people", # P1 FIX: Explicitly tag cards as people
                        metadata={
                            "type": "person_profile",
                            "is_card": True,
                            **name_title_meta
                        }
                    )
                    sections.append(section)
                    continue

            # Handle headings - they start new sections
            if element.name and element.name.startswith('h') and len(element.name) == 2:
                try:
                    level = int(element.name[1])
                    heading_text = element.get_text(strip=True)
                    
                    if not heading_text or len(heading_text) < 2:
                        continue
                    
                    if self._is_code_or_nav(heading_text):
                        continue
                    
                    # Flush previous section before starting new one
                    flush_section()
                    
                    # Update heading stack
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()
                    heading_stack.append((level, heading_text))
                    
                    # Start new section
                    current_heading = heading_text
                    current_level = level
                    
                except ValueError:
                    continue
            
            # Handle paragraphs
            elif element.name == 'p':
                text = element.get_text(separator=' ', strip=True)
                if len(text) >= 20 and not self._is_code_or_nav(text):
                    current_content.append(text)
            
            # Handle lists
            elif element.name in ['ul', 'ol']:
                items = []
                for li in element.find_all('li', recursive=False):
                    item_text = li.get_text(separator=' ', strip=True)
                    if len(item_text) > 5 and not self._is_code_or_nav(item_text):
                        items.append(f"• {item_text}")
                    processed_ids.add(id(li))
                
                if items:
                    current_content.append('\n'.join(items))
                    current_has_list = True
            
            # Handle tables
            elif element.name == 'table':
                table_text = self._extract_table_text(element)
                if table_text and len(table_text) > 20:
                    current_content.append(table_text)
                    current_has_table = True
                # Mark structure processed
                for child in element.find_all(True):
                    processed_ids.add(id(child))
            
            # Handle code blocks
            elif element.name == 'pre' or element.name == 'code':
                code_text = element.get_text(strip=True)
                if code_text and len(code_text) > 10:
                    current_content.append(f"```\n{code_text}\n```")
                    current_has_code = True
            
            # Handle blockquotes
            elif element.name == 'blockquote':
                quote_text = element.get_text(separator=' ', strip=True)
                if quote_text and len(quote_text) > 20:
                    current_content.append(f"> {quote_text}")
            
            # Handle divs (only leaf divs with direct text)
            elif element.name == 'div':
                # Only process if no block children (avoid duplication)
                if not element.find(['p', 'div', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table']):
                    text = element.get_text(separator=' ', strip=True)
                    if len(text) > 30 and not self._is_code_or_nav(text):
                        current_content.append(text)
        
        # Flush final section
        flush_section()
        
        return sections

    def _is_card_element(self, element: Tag) -> bool:
        """Check if element is a semantic card/profile."""
        if element.name not in ['div', 'article', 'section']:
            return False
            
        # Check classes
        classes = ' '.join(element.get('class', [])).lower()
        card_keywords = ['card', 'profile', 'member', 'employee', 'team-item', 'bio']
        if not any(kw in classes for kw in card_keywords):
            return False
            
        # Check text content pattern (Name + Title)
        # Fast check: should contain short lines
        text = element.get_text(strip=True)
        if len(text) > 500: # Too long for a typical card
            return False
            
        # Must contain a name-like structure (Capitalized words)
        if not re.search(r'[A-Z][a-z]+', text):
            return False
            
        return True

    def _extract_card_text(self, element: Tag) -> str:
        """Extract text from card preserving strict structure."""
        lines = []
        for child in element.find_all(['h1','h2','h3','h4','h5','p','span','div']):
             # Only leaf nodes or specific text wrappers
             if child.find(['p', 'div', 'h3']): 
                 continue
             t = child.get_text(strip=True)
             if t: lines.append(t)
        return '\n'.join(lines)

    def _extract_card_metadata(self, element: Tag) -> Dict:
        """Extract basic name/title for metadata."""
        meta = {}
        # Simple heuristic extraction
        text = element.get_text('\n', strip=True)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            meta['name'] = lines[0]
        if len(lines) > 1:
            meta['title'] = lines[1]
        return meta
    
    # -------------------------------------------------------------------------
    # 7. CONTENT QUALITY SCORING
    # -------------------------------------------------------------------------
    
    def score_content_quality(self, text: str, metadata: Dict) -> float:
        """
        Calculate content quality score using multiple dimensions.
        
        Scoring dimensions:
        1. Readability (0.2 weight): Sentence length variation, avg word length
        2. Vocabulary Diversity (0.2 weight): Unique words / total words
        3. Structural Richness (0.2 weight): has_code, has_list, has_table bonuses
        4. Informational Signals (0.25 weight): Numbers, proper nouns, technical terms
        5. Navigation Penalty (0.15 weight): Deduct for nav patterns, short lines
        
        Args:
            text: Section text to score
            metadata: Dict with keys: has_code, has_list, has_table, heading
            
        Returns:
            Normalized score between 0.0 and 1.0
        """
        if not text or len(text.strip()) < 20:
            return 0.0
        
        words = text.split()
        word_count = len(words)
        
        if word_count < 10:
            return 0.1
        
        # ---- Dimension 1: Readability (0.2) ----
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if sentences:
            sentence_lengths = [len(s.split()) for s in sentences]
            avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths)
            
            # Ideal sentence length is 15-25 words
            if 15 <= avg_sentence_length <= 25:
                readability_score = 1.0
            elif 10 <= avg_sentence_length < 15 or 25 < avg_sentence_length <= 35:
                readability_score = 0.7
            else:
                readability_score = 0.4
            
            # Sentence variety bonus
            if len(set(sentence_lengths)) > 2:
                readability_score = min(1.0, readability_score + 0.1)
        else:
            readability_score = 0.3
        
        # Average word length (ideal: 4-8 characters)
        avg_word_length = sum(len(w) for w in words) / word_count
        if 4 <= avg_word_length <= 8:
            readability_score = min(1.0, readability_score + 0.1)
        
        # ---- Dimension 2: Vocabulary Diversity (0.2) ----
        unique_words = set(w.lower() for w in words if len(w) > 2)
        vocab_diversity = len(unique_words) / word_count if word_count > 0 else 0
        
        # Normalize: 0.3-0.7 diversity is good
        if vocab_diversity >= 0.5:
            diversity_score = 1.0
        elif vocab_diversity >= 0.3:
            diversity_score = 0.8
        elif vocab_diversity >= 0.2:
            diversity_score = 0.5
        else:
            diversity_score = 0.3
        
        # ---- Dimension 3: Structural Richness (0.2) ----
        structure_score = 0.5  # Base score
        
        if metadata.get('has_code'):
            structure_score += 0.2
        if metadata.get('has_list'):
            structure_score += 0.15
        if metadata.get('has_table'):
            structure_score += 0.15
        if metadata.get('heading'):
            structure_score += 0.1
        
        structure_score = min(1.0, structure_score)
        
        # ---- Dimension 4: Informational Signals (0.25) ----
        info_score = 0.4  # Base score
        
        # Numbers and statistics
        number_pattern = r'\b\d+(?:\.\d+)?(?:\s*%|\s*[A-Za-z]+)?\b'
        numbers = re.findall(number_pattern, text)
        if len(numbers) >= 3:
            info_score += 0.2
        elif len(numbers) >= 1:
            info_score += 0.1
        
        # Proper nouns (capitalized words not at sentence start)
        proper_nouns = re.findall(r'(?<=[.!?]\s)[A-Z][a-z]+|(?<=\s)[A-Z][a-z]{2,}', text)
        if len(proper_nouns) >= 5:
            info_score += 0.2
        elif len(proper_nouns) >= 2:
            info_score += 0.1
        
        # Technical terms (words with mixed case, underscores, or camelCase)
        tech_terms = re.findall(r'\b[a-z]+[A-Z][a-zA-Z]*\b|\b\w+_\w+\b', text)
        if tech_terms:
            info_score += 0.1
        
        # Question words (informational content)
        question_words = len(re.findall(r'\b(what|how|why|when|where|who)\b', text, re.I))
        if question_words >= 2:
            info_score += 0.1
        
        info_score = min(1.0, info_score)
        
        # ---- Dimension 5: Navigation Penalty (0.15) ----
        nav_penalty = 0.0
        
        # Check for navigation patterns
        nav_patterns = [
            r'\bhome\b', r'\babout\s+us\b', r'\bcontact\b', r'\blogin\b',
            r'\bsign\s+in\b', r'\bsign\s+up\b', r'\bregister\b',
            r'\bmenu\b', r'\bsearch\b', r'\bsubscribe\b'
        ]
        for pattern in nav_patterns:
            if re.search(pattern, text, re.I):
                nav_penalty += 0.05
        
        # Penalty for too many short lines
        lines = text.split('\n')
        short_lines = sum(1 for line in lines if len(line.split()) < 4)
        if len(lines) > 0:
            short_line_ratio = short_lines / len(lines)
            if short_line_ratio > 0.5:
                nav_penalty += 0.2
        
        # Penalty for excessive links (URL patterns)
        url_count = len(re.findall(r'https?://', text))
        if url_count > word_count * 0.1:
            nav_penalty += 0.2
        
        nav_score = max(0.0, 1.0 - nav_penalty)
        
        # ---- Calculate final weighted score ----
        final_score = (
            readability_score * 0.20 +
            diversity_score * 0.20 +
            structure_score * 0.20 +
            info_score * 0.25 +
            nav_score * 0.15
        )
        
        # Ensure within bounds
        final_score = max(0.0, min(1.0, final_score))
        
        # Round to 2 decimal places
        return round(final_score, 2)
    
    # -------------------------------------------------------------------------
    # 8. DOMAIN INFERENCE
    # -------------------------------------------------------------------------
    
    def _infer_page_domain(self, url: str, title: str) -> str:
        """
        Infer the content domain based on URL patterns and title.
        
        Domains: "admin", "policy", "research", "history", "people", "general"
        """
        url_lower = url.lower()
        title_lower = title.lower()
        
        # 1. Admin / Policy
        if any(x in url_lower for x in ["/admin", "/policy", "/legal", "/terms", "/compliance", "policies"]):
            return "admin"
        if any(x in title_lower for x in ["policy", "compliance", "terms of use", "privacy", "administration"]):
            return "admin"
            
        # 2. People / Leadership (URL-based backstop if cards logic misses)
        if any(x in url_lower for x in ["/people", "/team", "/leadership", "/staff", "/profiles"]):
            return "people"
            
        # 3. History
        if any(x in url_lower for x in ["/history", "/about/story", "/timeline", "/legacy"]):
            return "history"
        if any(x in title_lower for x in ["our history", "company history", "legacy", "founding"]):
            return "history"
            
        # 4. Research
        if any(x in url_lower for x in ["/research", "/publications", "/whitepapers", "/case-studies"]):
            return "research"
            
        return "general"
    
    # -------------------------------------------------------------------------
    # LEGACY METHODS (Backward Compatibility)
    # -------------------------------------------------------------------------
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try <title> tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True)
        
        # Try h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        # Try og:title
        og_title = soup.find('meta', property='og:title')
        if og_title:
            return og_title.get('content', '')
        
        # Final fallback: use URL part (this will be improved in extract() anyway, but good to have here)
        return ""
    
    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """Extract meta description."""
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta:
            return meta.get('content', '')
        
        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            return og_desc.get('content', '')
        
        return ""
    
    def _extract_canonical(self, soup: BeautifulSoup, default_url: str) -> str:
        """Extract canonical URL."""
        canonical = soup.find('link', rel='canonical')
        if canonical:
            return canonical.get('href', default_url)
        return default_url
    
    def _find_main_content(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Legacy main content finder for backward compatibility."""
        return self.find_main_content_container(soup)
    
    def _remove_boilerplate(self, soup: BeautifulSoup):
        """Legacy boilerplate removal for backward compatibility."""
        self.remove_boilerplate_elements(soup)
    
    def _extract_semantic_blocks(self, container: Tag) -> List[SemanticBlock]:
        """Extract semantic blocks from content container (legacy format)."""
        blocks = []
        current_headers = []  # Stack of parent headers
        
        for element in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'table', 'pre', 'blockquote', 'div']):
            if element.name.startswith('h') and len(element.name) == 2:
                # Header element
                try:
                    level = int(element.name[1])
                    header_text = element.get_text(strip=True)
                    
                    if not header_text or len(header_text) < 2:
                        continue
                    
                    if self._is_code_or_nav(header_text):
                        continue
                    
                    # Update header stack
                    while current_headers and current_headers[-1][0] >= level:
                        current_headers.pop()
                    current_headers.append((level, header_text))
                    
                    blocks.append(SemanticBlock(
                        block_type="header",
                        content=header_text,
                        header=header_text,
                        header_level=level,
                        parent_headers=[h[1] for h in current_headers[:-1]]
                    ))
                except ValueError:
                    continue
                
            elif element.name == 'p':
                # Paragraph
                text = element.get_text(separator=' ', strip=True)
                if len(text) < 30:  # Skip short paragraphs
                    continue
                if self._is_code_or_nav(text):
                    continue
                
                blocks.append(SemanticBlock(
                    block_type="paragraph",
                    content=text,
                    header=current_headers[-1][1] if current_headers else None,
                    header_level=current_headers[-1][0] if current_headers else 0,
                    parent_headers=[h[1] for h in current_headers]
                ))
                
            elif element.name in ['ul', 'ol']:
                # List
                items = []
                for li in element.find_all('li', recursive=False):
                    item_text = li.get_text(separator=' ', strip=True)
                    if len(item_text) > 10 and not self._is_code_or_nav(item_text):
                        items.append(f"• {item_text}")
                
                if items:
                    blocks.append(SemanticBlock(
                        block_type="list",
                        content='\n'.join(items),
                        header=current_headers[-1][1] if current_headers else None,
                        header_level=current_headers[-1][0] if current_headers else 0,
                        parent_headers=[h[1] for h in current_headers]
                    ))
                    
            elif element.name == 'table':
                # Table - extract as structured text
                table_text = self._extract_table_text(element)
                if table_text and len(table_text) > 30:
                    blocks.append(SemanticBlock(
                        block_type="table",
                        content=table_text,
                        header=current_headers[-1][1] if current_headers else None,
                        header_level=current_headers[-1][0] if current_headers else 0,
                        parent_headers=[h[1] for h in current_headers]
                    ))
                    
            elif element.name == 'pre':
                # Code block
                code_text = element.get_text(strip=True)
                if code_text and len(code_text) > 20:
                    blocks.append(SemanticBlock(
                        block_type="code",
                        content=code_text,
                        header=current_headers[-1][1] if current_headers else None,
                        header_level=current_headers[-1][0] if current_headers else 0,
                        parent_headers=[h[1] for h in current_headers]
                    ))
                    
            elif element.name == 'blockquote':
                # Quote
                quote_text = element.get_text(separator=' ', strip=True)
                if quote_text and len(quote_text) > 20:
                    blocks.append(SemanticBlock(
                        block_type="quote",
                        content=quote_text,
                        header=current_headers[-1][1] if current_headers else None,
                        header_level=current_headers[-1][0] if current_headers else 0,
                        parent_headers=[h[1] for h in current_headers]
                    ))

            elif element.name == 'div':
                # Flexible div handling for non-standard CMS
                if not element.find(['p', 'div', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table']):
                    text = element.get_text(separator=' ', strip=True)
                    if len(text) > 30 and not self._is_code_or_nav(text):
                        blocks.append(SemanticBlock(
                            block_type="paragraph",
                            content=text,
                            header=current_headers[-1][1] if current_headers else None,
                            header_level=current_headers[-1][0] if current_headers else 0,
                            parent_headers=[h[1] for h in current_headers]
                        ))
        
        # Detect FAQ sections
        blocks = self._detect_faq_blocks(blocks)
        
        return blocks
    
    def _extract_table_text(self, table: Tag) -> str:
        """
        Extract table content as structured text.
        Special handling for person/contact tables for better RAG retrieval.
        """
        rows = []
        
        # Get headers
        headers = []
        header_lower = []
        thead = table.find('thead')
        if thead:
            for th in thead.find_all(['th', 'td']):
                header_text = th.get_text(strip=True)
                headers.append(header_text)
                header_lower.append(header_text.lower())
        
        # Also check first row for headers if no thead
        if not headers:
            first_row = table.find('tr')
            if first_row:
                for th in first_row.find_all(['th', 'td']):
                    header_text = th.get_text(strip=True)
                    headers.append(header_text)
                    header_lower.append(header_text.lower())
        
        # Detect if this is a person/contact table
        person_indicators = ['name', 'title', 'email', 'phone', 'address', 'role', 'position']
        is_person_table = any(
            any(indicator in h for indicator in person_indicators)
            for h in header_lower
        )
        
        # Find column indices for key fields
        name_idx = None
        title_idx = None
        email_idx = None
        phone_idx = None
        address_idx = None
        
        for i, h in enumerate(header_lower):
            if 'name' in h and name_idx is None:
                name_idx = i
            elif any(x in h for x in ['title', 'role', 'position']) and title_idx is None:
                title_idx = i
            elif 'email' in h and email_idx is None:
                email_idx = i
            elif 'phone' in h and phone_idx is None:
                phone_idx = i
            elif 'address' in h and address_idx is None:
                address_idx = i
        
        # Get body rows
        tbody = table.find('tbody') or table
        all_rows = tbody.find_all('tr')
        
        # Skip first row if it was used as headers
        start_idx = 1 if not thead and headers else 0
        
        for tr in all_rows[start_idx:]:
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if not cells or not any(cells):
                continue
            
            # For person tables, create natural language sentences
            if is_person_table and len(cells) >= 2:
                name = cells[name_idx] if name_idx is not None and name_idx < len(cells) else None
                title = cells[title_idx] if title_idx is not None and title_idx < len(cells) else None
                email = cells[email_idx] if email_idx is not None and email_idx < len(cells) else None
                phone = cells[phone_idx] if phone_idx is not None and phone_idx < len(cells) else None
                address = cells[address_idx] if address_idx is not None and address_idx < len(cells) else None
                
                if name:
                    person_sentences = []
                    
                    if title:
                        person_sentences.append(f"{name} works as a {title}.")
                        person_sentences.append(f"{name} is a {title}.")
                        first_name = name.split()[0] if name else ""
                        if first_name and first_name != name:
                            person_sentences.append(f"{first_name} ({name}) is a {title}.")
                    else:
                        person_sentences.append(f"{name} is a team member.")
                    
                    if email:
                        person_sentences.append(f"You can contact {name} via email at {email}.")
                    if phone:
                        person_sentences.append(f"The phone number for {name} is {phone}.")
                    if address:
                        person_sentences.append(f"{name} is located at {address}.")
                    
                    summary_parts = [f"{name}"]
                    if title:
                        summary_parts.append(f"({title})")
                    if email:
                        summary_parts.append(f"- Email: {email}")
                    if phone:
                        summary_parts.append(f"- Phone: {phone}")
                    if address:
                        summary_parts.append(f"- Location: {address}")
                    person_sentences.append(" ".join(summary_parts))
                    
                    rows.append(" ".join(person_sentences))
                else:
                    if headers and len(cells) == len(headers):
                        row_text = ' | '.join(f"{h}: {c}" for h, c in zip(headers, cells) if c)
                    else:
                        row_text = ' | '.join(c for c in cells if c)
                    if row_text:
                        rows.append(row_text)
            else:
                if headers and len(cells) == len(headers):
                    row_text = ' | '.join(f"{h}: {c}" for h, c in zip(headers, cells) if c)
                else:
                    row_text = ' | '.join(c for c in cells if c)
                if row_text:
                    rows.append(row_text)
        
        return '\n'.join(rows)
    
    def _detect_faq_blocks(self, blocks: List[SemanticBlock]) -> List[SemanticBlock]:
        """Detect and mark FAQ-style question/answer pairs."""
        faq_keywords = ['faq', 'frequently asked', 'questions', 'q&a', 'q & a']
        
        in_faq_section = False
        question_pattern = re.compile(r'^(what|how|why|when|where|who|can|do|does|is|are|will|would|should)\s', re.I)
        
        result = []
        i = 0
        while i < len(blocks):
            block = blocks[i]
            
            # Check if entering FAQ section
            if block.block_type == "header":
                header_lower = block.header.lower() if block.header else ""
                if any(kw in header_lower for kw in faq_keywords):
                    in_faq_section = True
            
            # Detect Q&A pairs
            if in_faq_section and block.block_type == "header":
                if question_pattern.match(block.content) or block.content.endswith('?'):
                    if i + 1 < len(blocks) and blocks[i + 1].block_type in ["paragraph", "list"]:
                        result.append(SemanticBlock(
                            block_type="faq",
                            content=f"Q: {block.content}\nA: {blocks[i + 1].content}",
                            header=block.header,
                            header_level=block.header_level,
                            parent_headers=block.parent_headers
                        ))
                        i += 2
                        continue
            
            result.append(block)
            i += 1
        
        return result
    
    def _is_code_or_nav(self, text: str) -> bool:
        """Check if text looks like CSS/JS code or navigation."""
        if not text or len(text) < 5:
            return False
        
        # Check CSS patterns
        for pattern in self.CSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Check JS patterns
        for pattern in self.JS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Check for excessive special characters
        if len(text) > 0:
            special_ratio = len(re.findall(r'[{}();:,\[\]<>]', text)) / len(text)
            if special_ratio > 0.3:
                return True
        
        # Common navigation words (short text only)
        if len(text) < 30:
            nav_words = ['menu', 'navigation', 'skip', 'home', 'login', 'sign in', 'search']
            text_lower = text.lower()
            if any(text_lower == nw or text_lower.startswith(nw + ' ') for nw in nav_words):
                return True
        
        return False
    
    def _build_raw_text(self, sections: List[SemanticBlock]) -> str:
        """Build plain text from semantic blocks (legacy)."""
        parts = []
        for block in sections:
            if block.block_type == "header":
                parts.append(f"\n\n{block.content}\n")
            else:
                parts.append(block.content)
        
        text = '\n'.join(parts)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def _build_raw_text_from_sections(self, sections: List[StructuredSection]) -> str:
        """Build plain text from structured sections."""
        parts = []
        for section in sections:
            if section.heading:
                parts.append(f"\n\n{section.heading}\n")
            parts.append(section.text)
        
        text = '\n'.join(parts)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
