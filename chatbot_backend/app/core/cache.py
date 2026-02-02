from cachetools import TTLCache
import logging
from typing import Tuple, Any, Optional

logger = logging.getLogger(__name__)

# Constants
RETRIEVAL_TTL = 900  # 15 minutes
ANSWER_TTL = 900     # 15 minutes
SHORT_TERM_TTL = 60  # 1 minute for NO_DATA or extensive failures
CACHE_VERSION = "v6"  # Increment this when making breaking changes to invalidate cached results

class RAGCache:
    """
    Singleton cache manager for RAG operations.
    enforces separation of concerns:
    - Retrieval Cache: Dense vector/chunk results.
    - Answer Cache: Final LLM answers.
    - Short-Term Cache: Failure states or empty results (NO_DATA).
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RAGCache, cls).__new__(cls)
            cls._instance._init_caches()
        return cls._instance

    def _init_caches(self):
        # Cache for expensive retrieval operations (post-filtering)
        self._retrieval_cache = TTLCache(maxsize=1000, ttl=RETRIEVAL_TTL)
        
        # Cache for final generated answers
        self._answer_cache = TTLCache(maxsize=1000, ttl=ANSWER_TTL)
        
        # Cache for "No Data" or empty results (Guardrail 2)
        # Prevents heavy retry loops on empty queries but expires quickly
        self._short_term_cache = TTLCache(maxsize=1000, ttl=SHORT_TERM_TTL)

    def get_retrieval(self, key: Tuple) -> Optional[Any]:
        """Get from retrieval cache or short-term cache (if it was an empty result)."""
        # check short term first (fast fail)
        if key in self._short_term_cache:
            return self._short_term_cache[key]
        return self._retrieval_cache.get(key)
        
    def set_retrieval(self, key: Tuple, value: Any):
        """
        Cache retrieval results.
        If value is empty/None, use short-term cache.
        """
        if not value:
            self._short_term_cache[key] = value
        else:
            self._retrieval_cache[key] = value

    def get_answer(self, key: Tuple) -> Optional[Any]:
        """Get from answer cache or short-term cache."""
        if key in self._short_term_cache:
            return self._short_term_cache[key]
        return self._answer_cache.get(key)

    def set_answer(self, key: Tuple, value: Any, is_no_data: bool = False):
        """
        Cache answer results.
        If is_no_data is True, use short-term cache.
        """
        if is_no_data:
            self._short_term_cache[key] = value
        else:
            self._answer_cache[key] = value
            
    def clear(self):
        """Clear all caches (useful for testing)."""
        self._retrieval_cache.clear()
        self._answer_cache.clear()
        self._short_term_cache.clear()

# Global Accessor
_rag_cache = RAGCache()

def get_rag_cache() -> RAGCache:
    return _rag_cache

# Alias for backward compatibility
get_cache = get_rag_cache

def generate_cache_key(
    collection_id: str, 
    intent: str, 
    query: str, 
    **kwargs
) -> Tuple:
    """
    Generate a normalized, immutable cache key.
    Basic structure: (version, collection_id, intent, normalized_query, ...kwargs)
    """
    normalized_query = query.strip().lower() if query else ""
    
    # Sort kwargs items for stability
    extra_items = tuple(sorted(kwargs.items()))
    
    # Include version to invalidate cache on code changes
    return (CACHE_VERSION, collection_id, intent, normalized_query) + extra_items