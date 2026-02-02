# app/services/crawler/image_analyzer.py
"""
Image Analyzer Module
Determines which images should be processed by OCR based on context, size, and metadata.
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple
from bs4 import Tag
from urllib.parse import urljoin, urlparse

logger = logging.getLogger("image_analyzer")

class ImageAnalyzer:
    """
    Analyzes images to determine if they are suitable candidates for OCR.
    Uses heuristics based on size, filename, alt text, and page context.
    """
    
    def __init__(self):
        # Compiled patterns for performance
        self.skip_filenames = re.compile(r'(icon|logo|button|arrow|bullet|separator|divider|social)', re.IGNORECASE)
        self.skip_classes = re.compile(r'(background|decoration|pattern|icon|logo)', re.IGNORECASE)
        self.content_filenames = re.compile(r'(team|staff|member|badge|card|profile|bio|headshot)', re.IGNORECASE)
        self.profile_classes = re.compile(r'(profile|team|member|person|staff|avatar|headshot)', re.IGNORECASE)
        
        # Extensions to skip (svg text is usually accessible via XML)
        self.skip_extensions = {'.svg', '.gif', '.ico'}
    
    def should_ocr_image(self, img_element: Tag, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an image element and decide if it should be OCR'd.
        
        Args:
            img_element: BeautifulSoup <img> tag
            context: Dictionary containing page context (page_type, page_url, etc.)
            
        Returns:
            Dict containing decision, priority, and metadata
        """
        # 1. Extract basic metadata
        src = img_element.get('src', '') or img_element.get('data-src', '') or img_element.get('data-lazy-src', '')
        
        # Handle srcset if src is missing or empty
        if not src and img_element.get('srcset'):
            # Simple srcset parsing: take the first logical URL
            srcset = img_element.get('srcset')
            src = srcset.split(',')[0].strip().split(' ')[0]
            
        if not src:
            return self._unknown_result("No source URL")
            
        # Resolve absolute URL
        if context.get('page_url'):
            full_url = urljoin(context['page_url'], src)
        else:
            full_url = src
            
        alt_text = (img_element.get('alt', '') or '').strip()
        
        # 2. Check for immediate skip conditions
        
        # skip SVG
        path = urlparse(full_url).path.lower()
        if any(path.endswith(ext) for ext in self.skip_extensions):
            return self._skip_result(full_url, "Skipped file extension")
            
        # Skip decoration/presentation
        if img_element.get('role') == 'presentation' or img_element.get('aria-hidden') == 'true':
            return self._skip_result(full_url, "Presentation role")
            
        # Skip comprehensive alt text (if it's long, we probably don't need OCR)
        # >15 words is likely a full description
        if len(alt_text.split()) > 15:
            return self._skip_result(full_url, "Comprehensive alt text exists", alt_text)
            
        # Check filename patterns (skip icons/logos)
        filename = path.split('/')[-1]
        if self.skip_filenames.search(filename):
            return self._skip_result(full_url, "Filename indicates icon/decoration")
            
        # Check class/id decoration patterns
        classes = " ".join(img_element.get('class', []))
        img_id = img_element.get('id', '')
        if self.skip_classes.search(classes) or self.skip_classes.search(img_id):
            if not self.profile_classes.search(classes) and not self.profile_classes.search(img_id):
                return self._skip_result(full_url, "CSS class indicates decoration")

        # 3. Calculate Score
        score = 0
        reasons = []
        
        # Context boost
        page_type = context.get('page_type', 'general')
        if page_type == 'team_page':
            score += 3
            reasons.append("Team page context")
        elif page_type == 'person_profile':
            score += 4
            reasons.append("Profile page context")
            
        # Parent Context (Person Card)
        parent_context = self._check_parent_context(img_element)
        if parent_context['is_person_card']:
            score += 3
            reasons.append("Inside person card")
            
        # Filename boost
        if self.content_filenames.search(filename):
            score += 2
            reasons.append("Filename matches person pattern")
            
        # Class boost
        if self.profile_classes.search(classes) or self.profile_classes.search(img_id):
            score += 2
            reasons.append("Class indicates person info")
            
        # Alt text signals (missing or generic)
        if not alt_text:
            score += 1
            reasons.append("Missing alt text")
        elif alt_text.lower() in ('image', 'photo', 'picture', 'profile'):
            score += 1
            reasons.append("Generic alt text")
            
        # Dynamic threshold adjustment for high people count
        # (Avoid processing too many images on massive lists)
        priority_threshold = 5
        people_count = context.get('people_count', 0)
        if people_count > 20:
             # Stricter threshold for dense pages
             # Only process if we are VERY sure (e.g. team page + person card)
             priority_threshold = 7
             reasons.append(f"High density page ({people_count} people), raising threshold")
        
        # 4. Final Decision
        should_ocr = score >= priority_threshold
        
        return {
            "should_ocr": should_ocr,
            "priority": min(score, 10),
            "reason": "; ".join(reasons) if reasons else "Low score",
            "image_url": full_url,
            "image_alt": alt_text,
            "context_type": "person_card" if parent_context['is_person_card'] else "general",
            "confidence": min(score / 10.0, 1.0)
        }

    def _check_parent_context(self, img_element: Tag) -> Dict[str, bool]:
        """Check up to 3 parent levels for 'person card' indicators."""
        current = img_element.parent
        for _ in range(3):
            if not current or current.name == 'body':
                break
                
            classes = " ".join(current.get('class', []))
            elem_id = current.get('id', '')
            
            if self.profile_classes.search(classes) or self.profile_classes.search(elem_id):
                return {"is_person_card": True}
                
            current = current.parent
            
        return {"is_person_card": False}

    def _skip_result(self, url: str, reason: str, alt: str = "") -> Dict[str, Any]:
        return {
            "should_ocr": False,
            "priority": 0,
            "reason": reason,
            "image_url": url,
            "image_alt": alt,
            "context_type": "general",
            "confidence": 0.0
        }
        
    def _unknown_result(self, reason: str) -> Dict[str, Any]:
        return {
            "should_ocr": False,
            "priority": 0,
            "reason": reason,
            "image_url": "",
            "image_alt": "",
            "context_type": "unknown",
            "confidence": 0.0
        }
