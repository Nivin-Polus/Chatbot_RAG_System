# app/core/vectorstore.py

import uuid
import logging
from app.config import settings
from app.core.embeddings import Embeddings

logger = logging.getLogger("vectorstore_logger")
logging.basicConfig(level=logging.INFO)

class VectorStore:
    def __init__(self, url=settings.VECTOR_DB_URL, collection_name="kb_docs"):
        self.collection_name = collection_name
        self.embeddings = Embeddings()
        self.url = url
        self._init_client()
        
    def _init_client(self):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import PointStruct, Distance
            self.client = QdrantClient(url=self.url)
            self.PointStruct = PointStruct
            self.Distance = Distance
            # Ensure collection exists
            self._ensure_collection()
            logger.info("Qdrant client initialized successfully")
        except Exception as e:
            logger.warning(f"Qdrant client initialization failed: {e}")
            logger.info("Using in-memory vector storage fallback")
            self.client = None
            self._init_fallback_storage()

    def _init_fallback_storage(self):
        """Initialize in-memory vector storage as fallback"""
        self.documents = {}  # id -> {vector, payload}
        
    def _ensure_collection(self):
        if self.client:
            try:
                self.client.get_collection(self.collection_name)
            except:
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config={"size": 384, "distance": self.Distance.COSINE}
                )
                logger.info(f"Qdrant collection '{self.collection_name}' created.")

    def add_document(self, doc_text: str, metadata: dict = None):
        vector = self.embeddings.encode(doc_text)
        doc_id = str(uuid.uuid4())
        
        if self.client:
            # Use Qdrant
            point = self.PointStruct(
                id=doc_id,
                vector=vector.tolist(),
                payload=metadata or {}
            )
            self.client.upsert(collection_name=self.collection_name, points=[point])
            logger.info(f"Document added to Qdrant: {metadata.get('file_name') if metadata else 'unknown'}")
        else:
            # Use fallback storage
            self.documents[doc_id] = {
                "vector": vector,
                "payload": metadata or {}
            }
            logger.info(f"Document added to memory: {metadata.get('file_name') if metadata else 'unknown'}")
        return doc_id

    def delete_document(self, point_id: str):
        if self.client:
            self.client.delete(collection_name=self.collection_name, points=[point_id])
            logger.info(f"Document deleted from Qdrant: {point_id}")
        else:
            if point_id in self.documents:
                del self.documents[point_id]
                logger.info(f"Document deleted from memory: {point_id}")

    def search(self, query: str, top_k: int = 5):
        query_vector = self.embeddings.encode(query)
        
        if self.client:
            # Use Qdrant
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector.tolist(),
                limit=top_k
            )
            return [{"payload": r.payload, "score": r.score} for r in results]
        else:
            # Use fallback: simple cosine similarity
            import numpy as np
            scores = []
            for doc_id, doc_data in self.documents.items():
                # Cosine similarity
                doc_vector = doc_data["vector"]
                similarity = np.dot(query_vector, doc_vector) / (np.linalg.norm(query_vector) * np.linalg.norm(doc_vector))
                scores.append({
                    "payload": doc_data["payload"],
                    "score": float(similarity),
                    "id": doc_id
                })
            
            # Sort by score and return top_k
            scores.sort(key=lambda x: x["score"], reverse=True)
            return scores[:top_k]
