# app/services/crawler/person_extractor.py
"""
Person Entity Extractor - Phase 1

Extracts person/team member information from HTML pages using multiple strategies:
1. Structured data (JSON-LD, Microdata) - highest confidence
2. HTML pattern detection - medium confidence
3. Semantic HTML parsing - lower confidence

Features:
- Confidence scoring for all extracted persons
- Deduplication with canonical identity rules
- Extraction safeguards (max people, min/max name length, noise filtering)
- Social link normalization
"""

import re
import logging
import hashlib
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger("person_extractor")


# =============================================================================
# CONSTANTS
# =============================================================================

# Confidence scores by extraction method
CONFIDENCE_STRUCTURED_DATA = 0.95
CONFIDENCE_HTML_PATTERN = 0.60
CONFIDENCE_SEMANTIC_HTML = 0.50

# Extraction limits
MAX_PEOPLE_PER_PAGE = 50
MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 100
MIN_TITLE_LENGTH = 2

# Team card class patterns (regex)
TEAM_CARD_PATTERNS = [
    r'team[-_]?member',
    r'person[-_]?card',
    r'staff[-_]?card',
    r'staff[-_]?member',
    r'employee[-_]?card',
    r'people[-_]?item',
    r'leader[-_]?card',
    r'leadership[-_]?card',
    r'bio[-_]?card',
    r'profile[-_]?card',
    r'team[-_]?card',
    r'member[-_]?card',
    r'author[-_]?card',
    r'speaker[-_]?card',
    r'executive[-_]?card',
    r'board[-_]?member',
]

# Noise patterns to exclude (elements to skip)
NOISE_PATTERNS = [
    r'testimonial',
    r'review',
    r'feedback',
    r'quote',
    r'related[-_]?post',
    r'suggested',
    r'recommended',
    r'footer',
    r'sidebar',
    r'widget',
    r'comment',
    r'social[-_]?share',
]

# Social platform normalization map
SOCIAL_PLATFORM_MAP = {
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "www.twitter.com": "twitter",
    "x.com": "twitter",
    "www.x.com": "twitter",
    "github.com": "github",
    "www.github.com": "github",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "medium.com": "medium",
    "www.medium.com": "medium",
}

# Name honorifics to remove during normalization
HONORIFICS = [
    "dr.", "dr", "mr.", "mr", "mrs.", "mrs", "ms.", "ms",
    "prof.", "prof", "sir", "dame", "rev.", "rev",
    "hon.", "hon", "phd", "ph.d", "md", "m.d",
]

# Standard header tags for name detection
HEADER_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']


# =============================================================================
# PERSON EXTRACTOR
# =============================================================================

class PersonExtractor:
    """
    Extracts person/team member information from HTML pages.
    
    Uses multiple strategies with different confidence levels:
    - Structured data: 0.95
    - HTML patterns: 0.60
    - Semantic HTML: 0.50
    
    Includes deduplication and noise filtering.
    """
    
    def __init__(self):
        """Initialize the extractor with compiled patterns."""
        self.team_card_pattern = re.compile(
            '|'.join(TEAM_CARD_PATTERNS),
            re.IGNORECASE
        )
        self.noise_pattern = re.compile(
            '|'.join(NOISE_PATTERNS),
            re.IGNORECASE
        )
    
    # -------------------------------------------------------------------------
    # MAIN EXTRACTION METHOD
    # -------------------------------------------------------------------------
    
    def extract_people(
        self, 
        soup: BeautifulSoup, 
        url: str, 
        structured_data: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Extract people from a page using multiple strategies.
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Page URL
            structured_data: Pre-extracted structured data (from StructuredDataExtractor)
            
        Returns:
            List of deduplicated person dictionaries
        """
        all_people = []
        
        # Strategy 1: Extract from structured data (highest priority)
        if structured_data:
            structured_persons = structured_data.get("persons", [])
            for person in structured_persons:
                # Already formatted by StructuredDataExtractor
                if self._validate_person(person):
                    all_people.append(person)
        
        # Strategy 2: Extract from HTML patterns
        html_people = self._extract_from_html_patterns(soup, url)
        all_people.extend(html_people)
        
        # Strategy 3: Extract from semantic HTML
        semantic_people = self._extract_from_semantic_html(soup, url)
        all_people.extend(semantic_people)
        
        # Deduplicate
        deduplicated = self._deduplicate_people(all_people, url)
        
        # Enforce max limit
        if len(deduplicated) > MAX_PEOPLE_PER_PAGE:
            logger.warning(f"Found {len(deduplicated)} people, limiting to {MAX_PEOPLE_PER_PAGE}")
            deduplicated = deduplicated[:MAX_PEOPLE_PER_PAGE]
        
        return deduplicated
    
    # -------------------------------------------------------------------------
    # STRATEGY 2: HTML PATTERN EXTRACTION
    # -------------------------------------------------------------------------
    
    def _extract_from_html_patterns(self, soup: BeautifulSoup, url: str) -> List[Dict]:
        """
        Extract people from repeating HTML patterns.
        
        Looks for:
        - Elements with team/person-related class names
        - Repeating structures with image + name + title pattern
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Page URL
            
        Returns:
            List of extracted person dictionaries
        """
        people = []
        processed_elements: Set[int] = set()
        
        # Find elements with team card classes
        for element in soup.find_all(True):
            element_id = id(element)
            if element_id in processed_elements:
                continue
            
            # Check if element matches team card patterns
            element_classes = ' '.join(element.get('class', []))
            element_id_attr = element.get('id', '')
            combined = f"{element_classes} {element_id_attr}"
            
            if not self.team_card_pattern.search(combined):
                continue
            
            # Skip if in noise region
            if self._is_in_noise_region(element):
                continue
            
            # Extract person from this element
            person = self._extract_person_from_card(element, url)
            if person and self._validate_person(person):
                people.append(person)
                processed_elements.add(element_id)
        
        # Also look for repeating structures (3+ similar patterns)
        repeating_people = self._find_repeating_person_patterns(soup, url, processed_elements)
        people.extend(repeating_people)
        
        # Strategy: Sibling sequence detection for flat vertical lists (NEW)
        sibling_people = self._extract_from_sibling_sequences(soup, url, processed_elements)
        people.extend(sibling_people)
        
        return people
    
    def _extract_from_sibling_sequences(
        self, 
        soup: BeautifulSoup, 
        url: str, 
        already_processed: Set[int]
    ) -> List[Dict]:
        """
        Detect people listed in a flat sequence of siblings (no wrapper card).
        Example: <h3>Name</h3><p>Title</p><a href="...">Social</a>
        """
        people = []
        
        # Find containers with many text-like children
        for container in soup.find_all(['div', 'section', 'main', 'article']):
            if self._is_in_noise_region(container):
                continue
                
            # Get all direct tag children
            children = [c for c in container.children if isinstance(c, Tag)]
            if len(children) < 5:
                continue
                
            # Iterate with a lookahead window
            i = 0
            while i < len(children):
                child = children[i]
                if id(child) in already_processed:
                    i += 1
                    continue
                
                # 1. Look for a Name Candidate
                text = child.get_text(strip=True)
                if not self._is_valid_name(text):
                    i += 1
                    continue
                
                # Score name candidate (Header or Bold is better)
                is_header = child.name in HEADER_TAGS or child.name in ['strong', 'b']
                # If not header, must be proper casing and reasonable length
                if not is_header and not (text[0].isupper() and len(text.split()) in (2, 3)):
                    i += 1
                    continue
                
                # 2. Lookahead for Title and Social (next 4 siblings)
                found_title = None
                found_socials = {}
                found_img = None
                
                for j in range(i + 1, min(i + 5, len(children))):
                    next_child = children[j]
                    if id(next_child) in already_processed:
                        continue
                        
                    next_text = next_child.get_text(strip=True)
                    
                    # Social Link?
                    if not found_socials:
                        socials = self._extract_social_links_from_card(next_child)
                        if socials:
                            found_socials = socials
                            continue
                            
                    # Image?
                    if not found_img:
                        img_url, _ = self._extract_image_from_card(next_child, url)
                        if img_url:
                            found_img = img_url
                            continue
                    
                    # Title?
                    if not found_title and next_text and next_text != text:
                        if self._is_likely_title_text(next_text):
                            found_title = next_text
                            continue
                
                # 3. If we found a Name + (Title OR Social OR Image), create person
                if text and (found_title or found_socials or found_img):
                    person = {
                        "name": text,
                        "title": found_title or "",
                        "description": None,
                        "image_url": found_img,
                        "social_links": found_socials,
                        "confidence": CONFIDENCE_HTML_PATTERN * 0.9, # Slightly lower than card-based
                        "extraction_method": "sibling_sequence",
                        "source": "html",
                        "source_urls": [url]
                    }
                    people.append(person)
                    
                    # Mark all used elements as processed
                    already_processed.add(id(child))
                    # Note: we don't necessarily mark following tags as processed 
                    # as they might be shared or ambiguous, but for the name tag it's vital.
                    
                    # Jump ahead? If we found a title specifically, we skip over it
                    # (Simplified: just move to next)
                    i += 1
                else:
                    i += 1
        
        return people
    
    def _is_likely_title_text(self, text: str) -> bool:
        """Check if string looks like a job title."""
        if not text or len(text) < 2 or len(text) > 100:
            return False
            
        common_titles = [
            'CEO', 'CTO', 'CFO', 'Director', 'Manager', 'Head', 'Lead', 
            'Chief', 'Officer', 'President', 'Vice', 'VP', 'Associate',
            'Engineer', 'Developer', 'Architect', 'Specialist', 'Consultant',
            'Founder', 'Partner', 'Principal', 'Senior', 'Junior', 'Staff'
        ]
        text_lower = text.lower()
        
        # Direct word match
        if any(f" {t.lower()} " in f" {text_lower} " for t in common_titles):
            return True
        if any(text_lower.startswith(t.lower()) for t in common_titles):
            return True
            
        return False
    
    def _extract_person_from_card(self, element: Tag, url: str) -> Optional[Dict]:
        """
        Extract person data from a card element.
        
        Looks for:
        - Image: <img> tag
        - Name: h2, h3, h4 or strong/b in specific positions
        - Title: p, span following name, or with specific classes
        - Social links: <a> with social platform URLs
        - Email: mailto: links
        
        Args:
            element: The card element
            url: Page URL
            
        Returns:
            Person dictionary or None
        """
        # Extract name
        name = self._extract_name_from_card(element)
        if not name:
            return None
        
        # Extract title/role
        title = self._extract_title_from_card(element, name)
        
        # --- FIX: Fail-Closed AI Title Validation (Refinement 4) ---
        if title:
            from app.services.leadership_classifier import leadership_classifier
            # Use concise context for validation (limit tokens)
            context_snippet = element.get_text(" ", strip=True)[:300]
            if not leadership_classifier.validate_title(title, context_snippet):
                # Fail-closed: Drop inferred/invalid title
                title = None
        
        # Extract description/bio
        description = self._extract_description_from_card(element, name, title)
        
        # Extract image
        image_url, image_alt = self._extract_image_from_card(element, url)
        
        # Extract social links
        social_links = self._extract_social_links_from_card(element)
        
        # Extract email
        email = self._extract_email_from_card(element)
        
        # Extract department (from section heading or parent context)
        department = self._extract_department(element)
        
        return {
            "name": name,
            "title": title,
            "description": description,
            "image_url": image_url,
            "image_alt": image_alt,
            "social_links": social_links,
            "email": email,
            "telephone": None,
            "department": department,
            "works_for": None,
            "alumni_of": None,
            "awards": None,
            "knows_about": None,
            "confidence": CONFIDENCE_HTML_PATTERN,
            "extraction_method": "html_pattern",
            "source": "html",
            "source_urls": [url]
        }
    
    def _extract_name_from_card(self, element: Tag) -> Optional[str]:
        """
        Extract person name from a card element.
        
        Priority:
        1. h2, h3, h4 tags
        2. Strong/b tags in first position
        3. Elements with name-related classes
        
        Args:
            element: The card element
            
        Returns:
            Name string or None
        """
        # Try heading tags first
        for tag_name in HEADER_TAGS:
            heading = element.find(tag_name)
            if heading:
                name = heading.get_text(strip=True)
                if self._is_valid_name(name):
                    return name
        
        # Try elements with name-related classes
        name_patterns = ['name', 'person-name', 'member-name', 'author-name', 'full-name']
        for pattern in name_patterns:
            name_el = element.find(class_=re.compile(pattern, re.IGNORECASE))
            if name_el:
                name = name_el.get_text(strip=True)
                if self._is_valid_name(name):
                    return name
        
        # Try strong/b in first text position
        for strong in element.find_all(['strong', 'b']):
            name = strong.get_text(strip=True)
            if self._is_valid_name(name):
                return name
        
        # Custom Fallback: If we have social links (strong signal), try first significant text
        # This handles cases where name is just in a <p> or <div> without class
        has_social = bool(element.find('a', href=re.compile(r'(linkedin|twitter|github)', re.IGNORECASE)))
        
        if has_social:
            # Look for first non-empty text element that looks like a name
            for tag in element.find_all(HEADER_TAGS + ['p', 'span', 'div', 'b', 'strong'], limit=5):
                text = tag.get_text(strip=True)
                # Must be 2-3 words, Title Case, not a social link text
                if (text and 
                    len(text.split()) in (2, 3) and 
                    text[0].isupper() and 
                    'linkedin' not in text.lower() and
                    self._is_valid_name(text)):
                    return text
        
        return None
    
    def _extract_title_from_card(self, element: Tag, name: str) -> Optional[str]:
        """
        Extract job title from a card element.
        
        Args:
            element: The card element
            name: The person's name (to avoid matching)
            
        Returns:
            Title string or None
        """
        # Try elements with title-related classes
        title_patterns = ['title', 'job-title', 'role', 'position', 'designation']
        for pattern in title_patterns:
            title_el = element.find(class_=re.compile(pattern, re.IGNORECASE))
            if title_el:
                title = title_el.get_text(strip=True)
                if title and title != name and len(title) >= MIN_TITLE_LENGTH:
                    return title
        
        # Try first <p> or <span> after heading
        headings = element.find_all(HEADER_TAGS)
        for heading in headings:
            # Get next sibling that's a p or span
            sibling = heading.find_next_sibling(['p', 'span'])
            if sibling:
                title = sibling.get_text(strip=True)
                if title and title != name and len(title) >= MIN_TITLE_LENGTH:
                    # Avoid long paragraphs (likely descriptions)
                    if len(title) < 100:
                        return title
        
        # Fallback: Look for text element immediately following the name element
        # Find the element containing the name text
        if name:
            # Search for the name in text nodes
            name_node = element.find(string=lambda t: t and name in t)
            if name_node:
                # Get the parent tag (e.g. <p>Name</p>)
                name_parent = name_node.parent
                
                # Check siblings
                next_sibling = name_parent.find_next_sibling(['p', 'span', 'div'])
                if next_sibling:
                    text = next_sibling.get_text(strip=True)
                    if (text and text != name and 
                        len(text) >= MIN_TITLE_LENGTH and len(text) < 100 and
                        'linkedin' not in text.lower()):
                        return text
                        
                # Check next element in traversal order (for flat structures)
                next_el = name_parent.find_next(['p', 'span', 'div'])
                if next_el and next_el != next_sibling:
                    text = next_el.get_text(strip=True)
                    if (text and text != name and 
                        len(text) >= MIN_TITLE_LENGTH and len(text) < 100 and
                        'linkedin' not in text.lower()):
                        return text

        return None
    
    def _extract_description_from_card(
        self, 
        element: Tag, 
        name: str, 
        title: Optional[str]
    ) -> Optional[str]:
        """
        Extract bio/description from a card element.
        
        Args:
            element: The card element
            name: Person's name (to exclude)
            title: Person's title (to exclude)
            
        Returns:
            Description string or None
        """
        # Look for description/bio classes
        desc_patterns = ['bio', 'description', 'about', 'summary', 'intro']
        for pattern in desc_patterns:
            desc_el = element.find(class_=re.compile(pattern, re.IGNORECASE))
            if desc_el:
                desc = desc_el.get_text(strip=True)
                if desc and desc != name and desc != title:
                    return desc
        
        # Look for longer paragraph text
        for p in element.find_all('p'):
            text = p.get_text(strip=True)
            # Skip if it's the name or title
            if text == name or text == title:
                continue
            # Look for substantial content (30+ chars)
            if len(text) >= 30:
                return text
        
        return None
    
    def _extract_image_from_card(
        self, 
        element: Tag, 
        url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract image URL and alt text from a card element.
        
        Args:
            element: The card element
            url: Page URL for resolving relative URLs
            
        Returns:
            Tuple of (image_url, image_alt)
        """
        img = element.find('img')
        if not img:
            return None, None
        
        # Get src (prefer data-src for lazy loading)
        src = img.get('data-src') or img.get('src')
        alt = img.get('alt', '')
        
        if not src:
            return None, alt
        
        # Resolve relative URL
        if src and not src.startswith(('http://', 'https://', '//')):
            src = urljoin(url, src)
        elif src and src.startswith('//'):
            src = 'https:' + src
        
        return src, alt or None
    
    def _extract_social_links_from_card(self, element: Tag) -> Dict[str, str]:
        """
        Extract social media links from a card element.
        
        Args:
            element: The card element
            
        Returns:
            Dictionary of platform -> URL
        """
        social_links = {}
        
        for a in element.find_all('a', href=True):
            href = a.get('href', '')
            if not href:
                continue
            
            platform = self._normalize_social_platform(href)
            if platform and platform not in social_links:
                social_links[platform] = href
        
        return social_links
    
    def _extract_email_from_card(self, element: Tag) -> Optional[str]:
        """
        Extract email from a card element.
        
        Args:
            element: The card element
            
        Returns:
            Email address or None
        """
        for a in element.find_all('a', href=True):
            href = a.get('href', '')
            if href.startswith('mailto:'):
                return href[7:]
        
        return None
    
    def _extract_department(self, element: Tag) -> Optional[str]:
        """
        Extract department from context.
        
        Looks for section headings above the card.
        
        Args:
            element: The card element
            
        Returns:
            Department name or None
        """
        # Look for parent section with heading
        parent = element.parent
        while parent:
            if parent.name in ['section', 'div']:
                # Check for heading in this section
                heading = parent.find(['h1', 'h2', 'h3'], recursive=False)
                if heading:
                    dept = heading.get_text(strip=True)
                    if dept and len(dept) < 50:
                        return dept
            parent = parent.parent
        
        return None
    
    # -------------------------------------------------------------------------
    # STRATEGY 3: SEMANTIC HTML EXTRACTION
    # -------------------------------------------------------------------------
    
    def _extract_from_semantic_html(self, soup: BeautifulSoup, url: str) -> List[Dict]:
        """
        Extract people from semantic HTML elements.
        
        Looks for:
        - <article> elements with person content
        - Elements with role="article" containing person info
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Page URL
            
        Returns:
            List of extracted person dictionaries
        """
        people = []
        
        # Find article elements
        for article in soup.find_all('article'):
            # Skip if in noise region
            if self._is_in_noise_region(article):
                continue
            
            # Check if this looks like a person article
            article_classes = ' '.join(article.get('class', []))
            if self.team_card_pattern.search(article_classes):
                person = self._extract_person_from_card(article, url)
                if person and self._validate_person(person):
                    person['confidence'] = CONFIDENCE_SEMANTIC_HTML
                    person['extraction_method'] = 'semantic_html'
                    people.append(person)
        
        return people
    
    # -------------------------------------------------------------------------
    # REPEATING PATTERN DETECTION
    # -------------------------------------------------------------------------
    
    def _find_repeating_person_patterns(
        self, 
        soup: BeautifulSoup, 
        url: str,
        already_processed: Set[int]
    ) -> List[Dict]:
        """
        Find repeating structures that look like person cards.
        
        Looks for 3+ similar sibling elements with person-like content.
        
        Args:
            soup: BeautifulSoup parsed HTML
            url: Page URL
            already_processed: Set of already processed element IDs
            
        Returns:
            List of extracted person dictionaries
        """
        people = []
        
        # Find containers with multiple similar children
        for container in soup.find_all(['div', 'ul', 'section']):
            if self._is_in_noise_region(container):
                continue
            
            # Get direct children of same type
            child_types = {}
            for child in container.children:
                if not isinstance(child, Tag):
                    continue
                if id(child) in already_processed:
                    continue
                
                child_signature = self._get_element_signature(child)
                if child_signature not in child_types:
                    child_types[child_signature] = []
                child_types[child_signature].append(child)
            
            # Find groups of 3+ similar elements
            for signature, elements in child_types.items():
                if len(elements) < 3:
                    continue
                
                # Check if these look like person cards
                extracted_people = []
                for el in elements:
                    person = self._extract_person_from_card(el, url)
                    if person and self._validate_person(person):
                        extracted_people.append(person)
                        already_processed.add(id(el))
                
                # If we got at least 3 valid people, add them
                if len(extracted_people) >= 3:
                    people.extend(extracted_people)
        
        return people
    
    def _get_element_signature(self, element: Tag) -> str:
        """
        Get a signature for element structure comparison.
        
        Args:
            element: The element
            
        Returns:
            Signature string
        """
        # Use tag name and class patterns
        tag = element.name or ''
        classes = sorted(element.get('class', []))
        
        # Count child types
        child_tags = [c.name for c in element.children if isinstance(c, Tag)]
        
        return f"{tag}:{','.join(classes)}:{','.join(sorted(set(child_tags)))}"
    
    # -------------------------------------------------------------------------
    # DEDUPLICATION
    # -------------------------------------------------------------------------
    
    def _deduplicate_people(self, people: List[Dict], url: str) -> List[Dict]:
        """
        Deduplicate people by canonical identity.
        
        Primary key: normalize(name) + image_url
        Fallback: normalize(name) + normalize(title) + page_url
        
        Merges:
        - source_urls from all matches
        - Uses highest confidence
        - Prefers structured_data extraction_method
        
        Args:
            people: List of person dictionaries
            url: Current page URL
            
        Returns:
            Deduplicated list
        """
        if not people:
            return []
        
        # Group by canonical ID
        groups: Dict[str, List[Dict]] = {}
        
        for person in people:
            canonical_id = self._get_canonical_id(person, url)
            if canonical_id not in groups:
                groups[canonical_id] = []
            groups[canonical_id].append(person)
        
        # Merge each group
        deduplicated = []
        for canonical_id, group in groups.items():
            merged = self._merge_person_group(group)
            if merged:
                deduplicated.append(merged)
        
        # Sort by confidence descending
        deduplicated.sort(key=lambda p: p.get('confidence', 0), reverse=True)
        
        return deduplicated
    
    def _get_canonical_id(self, person: Dict, url: str) -> str:
        """
        Get canonical identity for a person.
        
        Args:
            person: Person dictionary
            url: Page URL
            
        Returns:
            Canonical ID string
        """
        name = self._normalize_name(person.get('name', ''))
        image_url = person.get('image_url', '')
        title = self._normalize_name(person.get('title', ''))
        
        # Primary key: name + image_url
        if image_url:
            key = f"{name}|{image_url}"
        else:
            # Fallback: name + title + url
            key = f"{name}|{title}|{url}"
        
        return hashlib.sha256(key.encode()).hexdigest()[:16]
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize a name for comparison.
        
        - Lowercase
        - Remove honorifics
        - Collapse whitespace
        - Strip
        
        Args:
            name: Name to normalize
            
        Returns:
            Normalized name
        """
        if not name:
            return ""
        
        name = name.lower().strip()
        
        # Remove honorifics
        for honorific in HONORIFICS:
            name = re.sub(rf'\b{re.escape(honorific)}\b\.?\s*', '', name)
        
        # Collapse whitespace
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    def _merge_person_group(self, group: List[Dict]) -> Optional[Dict]:
        """
        Merge a group of duplicate persons.
        
        Args:
            group: List of person dictionaries
            
        Returns:
            Merged person dictionary
        """
        if not group:
            return None
        
        if len(group) == 1:
            return group[0]
        
        # Sort by confidence, prefer structured_data
        group.sort(key=lambda p: (
            p.get('extraction_method') == 'structured_data',
            p.get('confidence', 0)
        ), reverse=True)
        
        # Start with highest confidence
        merged = group[0].copy()
        
        # Collect all source URLs
        all_urls = set()
        all_methods = set()
        for person in group:
            all_urls.update(person.get('source_urls', []))
            all_methods.add(person.get('extraction_method', 'unknown'))
        
        merged['source_urls'] = list(all_urls)
        merged['extraction_methods'] = list(all_methods)
        
        # Fill in missing fields from other sources
        for person in group[1:]:
            for key, value in person.items():
                if key in ['source_urls', 'extraction_methods', 'confidence']:
                    continue
                if not merged.get(key) and value:
                    merged[key] = value
        
        return merged
    
    # -------------------------------------------------------------------------
    # VALIDATION HELPERS
    # -------------------------------------------------------------------------
    
    def _validate_person(self, person: Dict) -> bool:
        """
        Validate that a person dictionary is valid.
        
        Requirements:
        - Name is present and valid
        - Has at least one of: title, image_url, description
        
        Args:
            person: Person dictionary
            
        Returns:
            True if valid
        """
        name = person.get('name', '')
        if not self._is_valid_name(name):
            return False
        
        # Must have at least one additional field
        has_title = bool(person.get('title'))
        has_image = bool(person.get('image_url'))
        has_description = bool(person.get('description'))
        
        return has_title or has_image or has_description
    
    def _is_valid_name(self, name: str) -> bool:
        """Check if a string looks like a valid name."""
        if not name:
            return False
            
        # Check length
        if len(name) < MIN_NAME_LENGTH or len(name) > MAX_NAME_LENGTH:
            return False
            
        # Must contain letters
        if not any(c.isalpha() for c in name):
            return False
            
        # Should not contain common invalid chars
        if re.search(r'[{}<>@]', name):
            return False
            
        # Should not be a common noise word
        name_lower = name.lower()
        noise_words = ['read more', 'view profile', 'click here', 'social media', 'linkedin']
        if any(w in name_lower for w in noise_words):
            return False
            
        return True
    
    def _is_valid_name(self, name: str) -> bool:
        """
        Check if a name is valid.
        
        Args:
            name: Name to validate
            
        Returns:
            True if valid
        """
        if not name:
            return False
        
        name = name.strip()
        
        # Check length
        if len(name) < MIN_NAME_LENGTH or len(name) > MAX_NAME_LENGTH:
            return False
        
        # Should contain mostly letters and spaces
        alpha_ratio = sum(1 for c in name if c.isalpha() or c.isspace()) / len(name)
        if alpha_ratio < 0.7:
            return False
        
        # Should not be all uppercase (likely a heading/label)
        if name.isupper() and len(name) > 4:
            words = name.split()
            if len(words) > 3:  # Long all-caps is likely not a name
                return False
        
        return True
    
    def _is_in_noise_region(self, element: Tag) -> bool:
        """
        Check if element is in a noise region (footer, testimonials, etc.).
        
        Args:
            element: The element to check
            
        Returns:
            True if in noise region
        """
        # Check element itself
        element_classes = ' '.join(element.get('class', []))
        element_id = element.get('id', '')
        combined = f"{element_classes} {element_id}"
        
        if self.noise_pattern.search(combined):
            return True
        
        # Check ancestors
        parent = element.parent
        depth = 0
        while parent and depth < 5:
            if not isinstance(parent, Tag):
                break
            
            # Check tag name
            if parent.name in ['footer', 'aside']:
                return True
            
            # Check classes/id
            parent_classes = ' '.join(parent.get('class', []))
            parent_id = parent.get('id', '')
            combined = f"{parent_classes} {parent_id}"
            
            if self.noise_pattern.search(combined):
                return True
            
            parent = parent.parent
            depth += 1
        
        return False
    
    def _normalize_social_platform(self, url: str) -> Optional[str]:
        """
        Normalize a URL to a social platform name.
        
        Args:
            url: URL to normalize
            
        Returns:
            Platform name or None
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.netloc.lower()
            
            if ":" in hostname:
                hostname = hostname.split(":")[0]
            
            return SOCIAL_PLATFORM_MAP.get(hostname)
        except Exception:
            return None
