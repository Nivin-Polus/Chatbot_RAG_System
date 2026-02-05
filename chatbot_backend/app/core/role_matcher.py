"""
role_matcher.py

Semantic role → person matcher for person-first RAG.

Usage:
    from role_matcher import RoleMatcher
    
    matcher = RoleMatcher()
    score = matcher.match_role("HR", "Head of People Operations")
    # Returns: 0.78 (high match)
"""

import numpy as np
from typing import List, Tuple, Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class RoleMatcher:
    """
    Semantic role matcher using embedding similarity.
    
    Matches role queries (e.g., "HR manager") to person titles using
    embeddings, with no hardcoded role lists.
    
    Attributes:
        threshold: Minimum similarity score to consider a match (default: 0.6)
        embed_fn: Function to generate embeddings (must be provided)
        role_expansions: Optional dict of role aliases for boosting
    """
    
    def __init__(
        self,
        embed_fn: Callable[[str], List[float]],
        threshold: float = 0.6,
        role_expansions: Optional[Dict[str, List[str]]] = None
    ):
        """
        Initialize role matcher.
        
        Args:
            embed_fn: Function that takes text and returns embedding vector.
                     Should match the embedding model used for indexing.
            threshold: Minimum similarity score for match (0.0-1.0)
            role_expansions: Optional dict of role aliases, e.g.:
                            {"hr": ["human resources", "people ops", "talent"]}
        """
        self.embed_fn = embed_fn
        self.threshold = threshold
        self.role_expansions = role_expansions or {}
        
        # Cache for role embeddings to avoid re-computing
        self._embedding_cache = {}
    
    def match_role(self, query_role: str, person_title: str) -> float:
        """
        Compute semantic similarity between a role query and person title.
        
        Args:
            query_role: Role from query (e.g., "HR", "sales manager")
            person_title: Actual title (e.g., "HR Manager", "VP of Sales")
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize inputs
        query_role_norm = self._normalize_role(query_role)
        person_title_norm = self._normalize_role(person_title)
        
        if not query_role_norm or not person_title_norm:
            return 0.0
            
        # Get embeddings (with caching)
        query_vec = self._get_cached_embedding(query_role_norm)
        title_vec = self._get_cached_embedding(person_title_norm)
        
        # Compute similarity
        similarity = self._cosine_similarity(query_vec, title_vec)
        
        # Check for exact expansions (boost score)
        if self._check_role_expansion(query_role_norm, person_title_norm):
            similarity = min(1.0, similarity * 1.2)  # 20% boost for known aliases
        
        return similarity
    
    def find_role_owners(
        self,
        query_role: str,
        person_chunks: List[Dict],
        top_k: int = 5
    ) -> List[Tuple[Dict, float]]:
        """
        Find all people matching a role query, ranked by match score.
        """
        matches = []
        
        for chunk in person_chunks:
            # Extract person title from chunk metadata
            metadata = chunk.get("metadata", {})
            person_title = metadata.get("person_title", "")
            
            if not person_title or person_title.lower() == "unknown":
                continue
            
            # Compute match score
            score = self.match_role(query_role, person_title)
            
            # Only include if above threshold
            if score >= self.threshold:
                matches.append((chunk, score))
                logger.debug(
                    f"Role match: {query_role} -> {person_title} ({score:.3f})"
                )
        
        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches[:top_k]
    
    def extract_role_from_query(self, query: str) -> Optional[str]:
        """
        Extract role keyword from query.
        """
        query_lower = query.lower()
        
        # Common role keywords
        role_keywords = [
            "manager", "head", "director", "ceo", "cto", "cfo", "coo",
            "lead", "specialist", "coordinator", "officer", "president",
            "vp", "vice president", "chief", "hr", "sales", "marketing",
            "engineer", "developer", "designer", "analyst", "recruiter"
        ]
        
        # Find role keywords in query
        found_roles = []
        for keyword in role_keywords:
            if keyword in query_lower:
                found_roles.append(keyword)
        
        if not found_roles:
            return None
        
        # Check for composite roles like "hr manager"
        query_lower = query.lower()
        if "hr" in found_roles and "manager" in query_lower:
            return "hr manager"
            
        # Return longest match (most specific)
        found_roles.sort(key=len, reverse=True)
        return found_roles[0]
    
    def _normalize_role(self, role: str) -> str:
        """Normalize role text for better matching."""
        # Remove common noise words
        noise_words = {
            "the", "a", "an", "our", "their", "company", "team",
            "current", "new", "senior", "junior"
        }
        
        words = role.lower().replace("/", " ").replace("-", " ").split()
        words = [w for w in words if w not in noise_words]
        
        # Handle common abbreviations
        abbreviations = {
            "hr": "human resources",
            "ops": "operations",
            "vp": "vice president",
            "svp": "senior vice president",
            "evp": "executive vice president",
            "ceo": "chief executive officer",
            "cto": "chief technology officer",
            "cfo": "chief financial officer",
            "coo": "chief operating officer",
        }
        
        normalized = []
        for word in words:
            if word in abbreviations:
                normalized.extend(abbreviations[word].split())
            else:
                normalized.append(word)
        
        return " ".join(normalized)
    
    def _get_cached_embedding(self, text: str) -> np.ndarray:
        """Get embedding with caching to avoid recomputation."""
        if text not in self._embedding_cache:
            self._embedding_cache[text] = np.array(self.embed_fn(text))
        return self._embedding_cache[text]
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def _check_role_expansion(self, query_role: str, person_title: str) -> bool:
        """Check if person_title is a known expansion of query_role."""
        if not self.role_expansions:
            return False
        
        # Use normalized query for dict lookup
        query_role_norm = self._normalize_role(query_role)
        person_title_norm = self._normalize_role(person_title)
        
        for base_role, aliases in self.role_expansions.items():
            base_norm = self._normalize_role(base_role)
            if base_norm == query_role_norm:
                return any(self._normalize_role(a) in person_title_norm for a in aliases)
        
        return False

    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logger.info("Cleared role matcher embedding cache")
