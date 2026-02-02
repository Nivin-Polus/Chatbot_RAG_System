# app/core/embeddings.py

import numpy as np

class Embeddings:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Import here to avoid PyO3 initialization issues during module import
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
        except ImportError as e:
            print(f"Warning: Could not import sentence_transformers: {e}")
            self.model = None

    def encode(self, texts):
        """
        Returns a list of embeddings (numpy arrays) for the input texts.
        """
        if self.model is None:
            raise RuntimeError("Embeddings model not available - sentence_transformers not installed")

        if isinstance(texts, str):
            texts = [texts]
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings if len(embeddings) > 1 else embeddings[0]
