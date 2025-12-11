# app/services/crawler/content_extractor.py
"""
Semantic Content Extractor
Extracts structured content from HTML with section detection for optimal RAG performance.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from bs4 import BeautifulSoup, Tag
import logging

logger = logging.getLogger("content_extractor")


@dataclass
class SemanticBlock:
    """A semantic block of content with metadata."""
    
    block_type: str  # header, paragraph, list, table, faq, code
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


class ContentExtractor:
    """
    Extracts clean, structured content from HTML.
    Optimized for RAG by preserving semantic structure.
    """
    
    # Elements to remove completely
    REMOVE_TAGS = [
        'script', 'style', 'noscript', 'meta', 'link', 'head',
        'nav', 'footer', 'aside', 'header', 'form', 'button',
        'iframe', 'embed', 'object', 'svg', 'canvas'
    ]
    
    # Classes/IDs that indicate navigation/boilerplate
    REMOVE_PATTERNS = [
        r'nav', r'navigation', r'navbar', r'menu', r'main-menu',
        r'header', r'footer', r'site-footer', r'sidebar',
        r'breadcrumb', r'skip-link', r'social-share', r'share-buttons',
        r'ad\b', r'advertisement', r'ads', r'ad-container',
        r'cookie-banner', r'cookie-consent', r'popup', r'modal', r'overlay',
        r'toolbar', r'pagination', r'comment', r'comments'
    ]
    
    # CSS/JS code patterns
    CSS_PATTERNS = [
        r'^[\\.#@][\w\-]+[:\s\{]',
        r'[\w\-]+\s*:\s*[0-9]',
        r'\{[^}]{0,100}\}',
        r'px\s*;|em\s*;|rem\s*;|%\s*;',
    ]
    
    JS_PATTERNS = [
        r'^var\s+|^function\s+|^const\s+|^let\s+|^class\s+',
        r'=>|\(\)\s*=>|\bfunction\s*\(',
        r'document\.|window\.|console\.',
        r'\breturn\b.*;|\bif\s*\(|\bfor\s*\(|\bwhile\s*\(',
    ]
    
    def __init__(self):
        self.remove_pattern = re.compile(
            '|'.join(self.REMOVE_PATTERNS),
            re.IGNORECASE
        )
    
    def extract(self, html: str, url: str) -> Dict:
        """
        Extract structured content from HTML.
        
        Returns:
            Dict with:
                - title: Page title
                - sections: List of SemanticBlock objects
                - raw_text: Plain text version
                - metadata: Additional page metadata
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract metadata first
            title = self._extract_title(soup)
            meta_description = self._extract_meta_description(soup)
            canonical_url = self._extract_canonical(soup, url)
            
            # Remove unwanted elements
            self._remove_boilerplate(soup)
            
            # Find main content area
            main_content = self._find_main_content(soup)
            
            if not main_content:
                main_content = soup.find('body') or soup
            
            # Extract semantic blocks
            sections = self._extract_semantic_blocks(main_content)
            
            # Build raw text
            raw_text = self._build_raw_text(sections)
            
            return {
                "title": title,
                "url": url,
                "canonical_url": canonical_url,
                "meta_description": meta_description,
                "sections": sections,
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
                "sections": [],
                "raw_text": "",
                "word_count": 0,
                "error": str(e)
            }
    
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
    
    def _remove_boilerplate(self, soup: BeautifulSoup):
        """Remove navigation, ads, and other boilerplate content."""
        # Remove specific tags
        for tag in self.REMOVE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Remove elements with nav/menu classes/IDs
        # Must iterate over a list copy since we're modifying while iterating
        for element in list(soup.find_all(True)):
            try:
                # Safely get class attribute (can be list or None)
                class_attr = element.get('class', [])
                classes = ' '.join(class_attr) if class_attr else ''
                
                # Safely get id and role (can be string or None)
                element_id = element.get('id', '') or ''
                role = element.get('role', '') or ''
                
                # Check if element should be removed
                if self.remove_pattern.search(classes) or \
                   self.remove_pattern.search(element_id) or \
                   role in ['navigation', 'banner', 'contentinfo', 'complementary']:
                    element.decompose()
            except Exception:
                # Skip elements that can't be processed
                continue
    
    def _find_main_content(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the main content area of the page."""
        # Priority order for finding main content
        selectors = [
            ('main', {}),
            ('article', {}),
            ('div', {'role': 'main'}),
            ('div', {'id': re.compile(r'content|main|article', re.I)}),
            ('div', {'class': re.compile(r'content|main|article|post', re.I)}),
        ]
        
        for tag, attrs in selectors:
            element = soup.find(tag, attrs)
            if element and len(element.get_text(strip=True)) > 100:
                return element
        
        return None
    
    def _extract_semantic_blocks(self, container: Tag) -> List[SemanticBlock]:
        """Extract semantic blocks from content container."""
        blocks = []
        current_headers = []  # Stack of parent headers
        
        for element in container.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'table', 'pre', 'blockquote']):
            if element.name.startswith('h') and len(element.name) == 2:
                # Header element
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
        
        # Detect FAQ sections
        blocks = self._detect_faq_blocks(blocks)
        
        return blocks
    
    def _extract_table_text(self, table: Tag) -> str:
        """Extract table content as structured text."""
        rows = []
        
        # Get headers
        headers = []
        thead = table.find('thead')
        if thead:
            for th in thead.find_all(['th', 'td']):
                headers.append(th.get_text(strip=True))
        
        # Get body rows
        tbody = table.find('tbody') or table
        for tr in tbody.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if cells and any(cells):
                if headers and len(cells) == len(headers):
                    row_text = ' | '.join(f"{h}: {c}" for h, c in zip(headers, cells))
                else:
                    row_text = ' | '.join(cells)
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
                    # This is likely a question
                    if i + 1 < len(blocks) and blocks[i + 1].block_type in ["paragraph", "list"]:
                        # Combine question and answer
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
        """Build plain text from semantic blocks."""
        parts = []
        for block in sections:
            if block.block_type == "header":
                parts.append(f"\n\n{block.content}\n")
            else:
                parts.append(block.content)
        
        text = '\n'.join(parts)
        # Clean up excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
