import threading
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None

def get_embedding_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    """
    Returns a thread-safe singleton instance of SentenceTransformer.
    Loads the model only once.
    """
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                logger.info("SentenceTransformer singleton initialized")
                _model = SentenceTransformer(model_name)
    return _model
