# app/core/vectorstore.py

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, Distance
from app.config import settings
from app.core.embeddings import Embeddings
import uuid
import logging

logger = logging.getLogger("vectorstore_logger")
logging.basicConfig(level=logging.INFO)

class VectorStore:
    def __init__(self, url=settings.VECTOR_DB_URL, collection_name="kb_docs"):
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)
        self.embeddings = Embeddings()
        # Ensure collection exists
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
        except:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config={"size": 384, "distance": Distance.COSINE}
            )
            logger.info(f"Qdrant collection '{self.collection_name}' created.")

    def add_document(self, doc_text: str, metadata: dict = None):
        vector = self.embeddings.encode(doc_text)
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector.tolist(),
            payload=metadata or {}
        )
        self.client.upsert(collection_name=self.collection_name, points=[point])
        logger.info(f"Document added to Qdrant: {metadata.get('file_name') if metadata else 'unknown'}")

    def delete_document(self, point_id: str):
        self.client.delete(collection_name=self.collection_name, points=[point_id])
        logger.info(f"Document deleted from Qdrant: {point_id}")

    def search(self, query: str, top_k: int = 5):
        query_vector = self.embeddings.encode(query)
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=top_k
        )
        # Return list of dicts with payload and score
        return [{"payload": r.payload, "score": r.score} for r in results]
