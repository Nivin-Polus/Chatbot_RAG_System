# app/core/background_cache.py
"""
Background cache manager for expensive operations that shouldn't block requests.
Uses in-memory caching with thread-safe access.
"""

import threading
import time
import logging
from typing import List, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class PersonCacheManager:
    """
    Thread-safe singleton for background person name caching.
    
    This moves the expensive 9 Qdrant scroll calls out of the request path
    by maintaining a pre-fetched list of known person names in memory.
    
    The cache is refreshed:
    - On startup (async, non-blocking)
    - Every refresh_interval seconds via background thread
    - On-demand when refresh_now() is called (e.g., after crawl completion)
    """
    
    _instance: Optional["PersonCacheManager"] = None
    _init_lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._cache: List[str] = []
        self._cache_lock = threading.RLock()
        self._last_refresh: float = 0
        self._refresh_interval: int = 3600  # 1 hour
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._vector_store = None  # Lazy loaded
        self._initialized = True
        logger.info("[PersonCacheManager] Initialized (empty cache)")
    
    def _get_vector_store(self):
        """Lazy load vector store to avoid circular imports."""
        if self._vector_store is None:
            try:
                from app.core.vectorstore import VectorStore
                self._vector_store = VectorStore()
            except Exception as e:
                logger.error(f"[PersonCacheManager] Failed to init VectorStore: {e}")
        return self._vector_store
    
    def get_cached_people(self) -> List[str]:
        """
        Get the cached list of known person names.
        Thread-safe, O(1) read access, zero latency.
        
        Returns:
            List of known person names (may be empty if not yet refreshed)
        """
        with self._cache_lock:
            return self._cache.copy()
    
    def get_cache_age_seconds(self) -> float:
        """Get how old the cache is in seconds."""
        if self._last_refresh == 0:
            return float('inf')
        return time.time() - self._last_refresh
    
    def refresh_now(self, force: bool = False) -> bool:
        """
        Synchronously refresh the cache.
        
        Args:
            force: If True, refresh even if cache is fresh
            
        Returns:
            True if refresh was performed, False if skipped
        """
        current_time = time.time()
        
        # Skip if cache is fresh (unless forced)
        if not force and (current_time - self._last_refresh) < self._refresh_interval:
            logger.debug("[PersonCacheManager] Cache still fresh, skipping refresh")
            return False
        
        return self._do_refresh()
    
    def _do_refresh(self) -> bool:
        """Actually perform the refresh operation."""
        vector_store = self._get_vector_store()
        if not vector_store:
            logger.warning("[PersonCacheManager] No vector store available")
            return False
        
        try:
            start_time = time.time()
            
            # This is the expensive operation we're moving out of request path
            names = vector_store.get_all_unique_values(
                field="person_name",
                filter_key="chunk_type",
                filter_value="person_profile",
                allow_unsafe_scroll=True
            )
            
            # Filter valid names
            valid_names = [
                n for n in names 
                if n and isinstance(n, str) and len(n.split()) >= 1
            ]
            
            elapsed = time.time() - start_time
            
            # Update cache atomically
            with self._cache_lock:
                self._cache = valid_names
                self._last_refresh = time.time()
            
            logger.info(
                f"[PersonCacheManager] Refreshed: {len(valid_names)} people in {elapsed:.2f}s"
            )
            return True
            
        except Exception as e:
            logger.error(f"[PersonCacheManager] Refresh failed: {e}")
            return False
    
    def start_background_refresh(self):
        """
        Start the background refresh thread.
        Should be called once on app startup.
        """
        if self._refresh_thread and self._refresh_thread.is_alive():
            logger.warning("[PersonCacheManager] Background refresh already running")
            return
        
        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._background_refresh_loop,
            name="PersonCacheRefresh",
            daemon=True  # Won't block app shutdown
        )
        self._refresh_thread.start()
        logger.info("[PersonCacheManager] Background refresh thread started")
    
    def stop_background_refresh(self):
        """Stop the background refresh thread."""
        self._stop_event.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
            logger.info("[PersonCacheManager] Background refresh thread stopped")
    
    def _background_refresh_loop(self):
        """Background thread loop that refreshes cache periodically."""
        # Initial refresh on startup
        logger.info("[PersonCacheManager] Performing initial refresh...")
        self._do_refresh()
        
        while not self._stop_event.is_set():
            # Wait for next refresh interval (or until stopped)
            self._stop_event.wait(timeout=self._refresh_interval)
            
            if not self._stop_event.is_set():
                logger.debug("[PersonCacheManager] Periodic refresh triggered")
                self._do_refresh()


# Global accessor
_person_cache_manager: Optional[PersonCacheManager] = None
_manager_lock = threading.Lock()


def get_person_cache_manager() -> PersonCacheManager:
    """Get the singleton PersonCacheManager instance."""
    global _person_cache_manager
    if _person_cache_manager is None:
        with _manager_lock:
            if _person_cache_manager is None:
                _person_cache_manager = PersonCacheManager()
    return _person_cache_manager


# Convenience function for RAG service
def get_known_people() -> List[str]:
    """Get cached known person names (zero latency)."""
    return get_person_cache_manager().get_cached_people()


# Hook for crawler completion
def trigger_person_cache_refresh():
    """
    Trigger an immediate cache refresh.
    Call this after crawl completion to pick up new people.
    """
    logger.info("[PersonCacheManager] Manual refresh triggered")
    get_person_cache_manager().refresh_now(force=True)
