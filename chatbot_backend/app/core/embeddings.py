# app/core/embeddings.py

from sentence_transformers import SentenceTransformer
import numpy as np

class Embeddings:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def encode(self, texts):
        """
        Returns a list of embeddings (numpy arrays) for the input texts.
        """
        if isinstance(texts, str):
            texts = [texts]
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings if len(embeddings) > 1 else embeddings[0]
