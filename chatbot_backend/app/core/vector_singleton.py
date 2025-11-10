# app/core/vector_singleton.py

from app.core.vectorstore import VectorStore
from app.config import settings

# Global singleton instance
_vector_store_instance = None

def get_vector_store() -> VectorStore:
    """Get the singleton vector store instance"""
    global _vector_store_instance
    
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore(settings.VECTOR_DB_URL)
    
    return _vector_store_instance
