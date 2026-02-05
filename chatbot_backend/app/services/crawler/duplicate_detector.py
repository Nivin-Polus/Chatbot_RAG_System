# app/services/crawler/duplicate_detector.py
"""
Duplicate Page Detector
Uses SimHash for near-duplicate detection to prevent RAG pollution.
"""

import re
import hashlib
from typing import Set, Dict, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger("duplicate_detector")


class SimHash:
    """
    SimHash implementation for near-duplicate text detection.
    
    SimHash creates a fingerprint where similar documents have
    similar fingerprints, allowing efficient similarity comparison.
    """
    
    def __init__(self, hash_bits: int = 64):
        self.hash_bits = hash_bits
    
    def hash(self, text: str) -> int:
        """
        Generate SimHash fingerprint for text.
        
        Args:
            text: Input text
            
        Returns:
            Integer fingerprint
        """
        # Tokenize (use word n-grams for better accuracy)
        tokens = self._tokenize(text)
        
        if not tokens:
            return 0
        
        # Initialize bit vector
        v = [0] * self.hash_bits
        
        # Hash each token and update vector
        for token in tokens:
            token_hash = self._hash_token(token)
            for i in range(self.hash_bits):
                bit = (token_hash >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1
        
        # Generate final hash
        fingerprint = 0
        for i in range(self.hash_bits):
            if v[i] > 0:
                fingerprint |= (1 << i)
        
        return fingerprint
    
    def _tokenize(self, text: str) -> list:
        """Tokenize text into words and 2-grams."""
        # Clean and lowercase
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        
        tokens = words.copy()
        
        # Add 2-grams
        for i in range(len(words) - 1):
            tokens.append(f"{words[i]}_{words[i+1]}")
        
        return tokens
    
    def _hash_token(self, token: str) -> int:
        """Hash a single token to 64-bit integer."""
        h = hashlib.md5(token.encode()).digest()
        return int.from_bytes(h[:8], 'little')
    
    def hamming_distance(self, hash1: int, hash2: int) -> int:
        """Calculate Hamming distance between two hashes."""
        xor = hash1 ^ hash2
        distance = 0
        while xor:
            distance += xor & 1
            xor >>= 1
        return distance
    
    def similarity(self, hash1: int, hash2: int) -> float:
        """
        Calculate similarity between two hashes.
        
        Returns:
            Float between 0 (completely different) and 1 (identical)
        """
        distance = self.hamming_distance(hash1, hash2)
        return 1 - (distance / self.hash_bits)


class DuplicateDetector:
    """
    Detects duplicate and near-duplicate pages during crawling.
    
    Uses multiple strategies:
    1. Exact URL matching (with normalization)
    2. Content hash (exact duplicates)
    3. SimHash (near-duplicates)
    4. Title + content length (quick filter)
    """
    
    def __init__(self, similarity_threshold: float = 0.90):
        """
        Initialize duplicate detector.
        
        Args:
            similarity_threshold: Minimum similarity to consider as duplicate (0-1)
        """
        self.similarity_threshold = similarity_threshold
        self.simhasher = SimHash()
        
        # Storage for seen content
        self.url_hashes: Set[str] = set()  # Normalized URLs
        self.content_hashes: Set[str] = set()  # MD5 of content
        self.simhashes: Dict[int, str] = {}  # SimHash -> URL mapping
        self.title_signatures: Dict[str, str] = {}  # Title+length -> URL
        
        # Pagination detection
        self.url_patterns: Dict[str, int] = defaultdict(int)  # Pattern -> count
        self.max_pagination_pages = 50
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
        
        parsed = urlparse(url)
        
        # Remove fragment
        # Sort query parameters
        query_params = sorted(parse_qsl(parsed.query))
        
        # Remove common tracking parameters
        tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 
                          'utm_content', 'ref', 'source', 'fbclid', 'gclid'}
        query_params = [(k, v) for k, v in query_params if k not in tracking_params]
        
        # Reconstruct URL
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip('/') or '/',
            parsed.params,
            urlencode(query_params),
            ''  # Remove fragment
        ))
        
        return normalized
    
    def is_duplicate(self, url: str, content: str, title: str = "") -> Tuple[bool, str]:
        """
        Check if a page is a duplicate.
        
        Args:
            url: Page URL
            content: Page text content
            title: Page title
            
        Returns:
            Tuple of (is_duplicate, reason)
        """
        # 1. Check URL
        normalized_url = self.normalize_url(url)
        url_hash = hashlib.md5(normalized_url.encode()).hexdigest()
        
        if url_hash in self.url_hashes:
            return True, "duplicate_url"
        
        # 2. Check pagination pattern
        if self._is_pagination_duplicate(url):
            return True, "pagination_loop"
        
        # 3. Check exact content match
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        if content_hash in self.content_hashes:
            return True, "exact_duplicate"
        
        # 4. Check title + length signature (quick filter)
        if title:
            content_length = len(content)
            # Round length to nearest 500 chars
            length_bucket = (content_length // 500) * 500
            signature = f"{title.lower()}:{length_bucket}"
            
            if signature in self.title_signatures:
                # Potential duplicate, do full SimHash check
                pass
        
        # 5. Check SimHash for near-duplicates
        if len(content) > 200:  # Only SimHash substantial content
            simhash = self.simhasher.hash(content)
            
            for existing_hash, existing_url in self.simhashes.items():
                similarity = self.simhasher.similarity(simhash, existing_hash)
                if similarity >= self.similarity_threshold:
                    logger.info(f"Near-duplicate detected: {url} similar to {existing_url} ({similarity:.2%})")
                    return True, f"near_duplicate:{similarity:.2%}"
            
            # Store for future comparisons
            self.simhashes[simhash] = url
        
        # Not a duplicate, remember this page
        self.url_hashes.add(url_hash)
        self.content_hashes.add(content_hash)
        if title:
            self.title_signatures[signature] = url
        
        return False, ""
    
    def _is_pagination_duplicate(self, url: str) -> bool:
        """Detect if URL is part of a pagination loop we've already crawled."""
        from urllib.parse import urlparse, parse_qsl
        
        parsed = urlparse(url)
        
        # Check for common pagination patterns
        pagination_params = ['page', 'p', 'pg', 'offset', 'start']
        query_params = dict(parse_qsl(parsed.query))
        
        for param in pagination_params:
            if param in query_params:
                # Create pattern key without the page number
                pattern_params = {k: v for k, v in query_params.items() if k != param}
                pattern_key = f"{parsed.netloc}{parsed.path}?{sorted(pattern_params.items())}"
                
                self.url_patterns[pattern_key] += 1
                
                if self.url_patterns[pattern_key] > self.max_pagination_pages:
                    logger.info(f"Pagination limit reached for pattern: {pattern_key}")
                    return True
        
        # Check path-based pagination (/page/2, /page/3, etc.)
        path_match = re.search(r'/page/(\d+)', parsed.path)
        if path_match:
            base_path = re.sub(r'/page/\d+', '', parsed.path)
            pattern_key = f"{parsed.netloc}{base_path}"
            
            self.url_patterns[pattern_key] += 1
            
            if self.url_patterns[pattern_key] > self.max_pagination_pages:
                return True
        
        return False
    
    def reset(self):
        """Reset all stored data."""
        self.url_hashes.clear()
        self.content_hashes.clear()
        self.simhashes.clear()
        self.title_signatures.clear()
        self.url_patterns.clear()
    
    def get_stats(self) -> Dict:
        """Get detector statistics."""
        return {
            "urls_seen": len(self.url_hashes),
            "content_hashes": len(self.content_hashes),
            "simhashes": len(self.simhashes),
            "pagination_patterns": len(self.url_patterns)
        }
