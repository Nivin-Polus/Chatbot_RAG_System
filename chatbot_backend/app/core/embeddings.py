# app/core/embeddings.py

import numpy as np
import logging

logger = logging.getLogger(__name__)

class Embeddings:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Import here to avoid PyO3 initialization issues during module import
        try:
            from app.core.model_singleton import get_embedding_model
            self.model = get_embedding_model(model_name)
        except ImportError as e:
            print(f"Warning: Could not import sentence_transformers: {e}")
            self.model = None

    def encode(self, texts, use_cache: bool = True):
        """
        Returns a list of embeddings (numpy arrays) for the input texts.
        Uses RAGCache for caching repeated query embeddings.
        
        Args:
            texts: Single text or list of texts to encode
            use_cache: Whether to use embedding cache (default True)
        """
        if self.model is None:
            raise RuntimeError("Embeddings model not available - sentence_transformers not installed")

        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]
        
        # Check cache for single queries (common case)
        if use_cache and single_input:
            try:
                from app.core.cache import get_rag_cache
                cache = get_rag_cache()
                cached = cache.get_embedding(texts[0])
                if cached is not None:
                    logger.debug(f"[Embeddings] Cache hit for query")
                    return cached
            except Exception:
                pass  # Cache miss or error, proceed to compute
        
        # Compute embeddings
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        result = embeddings if len(embeddings) > 1 else embeddings[0]
        
        # Cache single query embeddings
        if use_cache and single_input:
            try:
                from app.core.cache import get_rag_cache
                cache = get_rag_cache()
                cache.set_embedding(texts[0], result)
            except Exception:
                pass  # Cache write error, non-critical
        
        return result

