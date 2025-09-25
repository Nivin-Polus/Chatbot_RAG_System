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
                # Try to check if collection exists using collection_exists method
                if self.client.collection_exists(self.collection_name):
                    logger.info(f"Qdrant collection '{self.collection_name}' already exists.")
                    return
            except:
                # If collection_exists method doesn't work, try alternative approach
                pass
            
            try:
                # Try to create collection - if it exists, this will fail with 409
                from qdrant_client.http.models import VectorParams
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=self.Distance.COSINE)
                )
                logger.info(f"Qdrant collection '{self.collection_name}' created.")
            except Exception as create_error:
                if "already exists" in str(create_error):
                    logger.info(f"Qdrant collection '{self.collection_name}' already exists.")
                else:
                    logger.error(f"Failed to create collection: {create_error}")
                    raise

    def add_document(self, doc_text: str, metadata: dict = None):
        # Ensure collection exists before adding documents
        self._ensure_collection()
        
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

    def add_documents_with_metadata(self, documents: list[dict]):
        """Bulk add documents where each item has text and payload metadata"""
        if not documents:
            return []

        self._ensure_collection()
        inserted_ids = []

        if self.client:
            points = []
            for doc in documents:
                text = doc.get("text", "")
                payload = doc.get("metadata", {})
                vector = self.embeddings.encode(text)
                doc_id = str(uuid.uuid4())
                inserted_ids.append(doc_id)
                points.append(
                    self.PointStruct(
                        id=doc_id,
                        vector=vector.tolist(),
                        payload=payload
                    )
                )
            if points:
                self.client.upsert(collection_name=self.collection_name, points=points)
        else:
            for doc in documents:
                text = doc.get("text", "")
                payload = doc.get("metadata", {})
                vector = self.embeddings.encode(text)
                doc_id = str(uuid.uuid4())
                inserted_ids.append(doc_id)
                self.documents[doc_id] = {
                    "vector": vector,
                    "payload": payload
                }

        return inserted_ids

    def delete_document(self, point_id: str):
        if self.client:
            self.client.delete(collection_name=self.collection_name, points=[point_id])
            logger.info(f"Document deleted from Qdrant: {point_id}")
        else:
            if point_id in self.documents:
                del self.documents[point_id]
                logger.info(f"Document deleted from memory: {point_id}")

    def delete_documents_by_file_id(self, file_id: str):
        """Delete all document chunks belonging to a specific file"""
        if self.client:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            # Delete all points with matching file_id in payload
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="file_id",
                            match=MatchValue(value=file_id)
                        )
                    ]
                )
            )
            logger.info(f"All chunks for file {file_id} deleted from Qdrant")
        else:
            # For fallback storage, delete all documents with matching file_id
            to_delete = []
            for doc_id, doc_data in self.documents.items():
                if doc_data["payload"].get("file_id") == file_id:
                    to_delete.append(doc_id)
            for doc_id in to_delete:
                del self.documents[doc_id]
            logger.info(f"Deleted {len(to_delete)} chunks for file {file_id} from memory")
            return len(to_delete)

    def search(self, query: str, top_k: int = 5, collection_id: str = None):
        query_vector = self.embeddings.encode(query)
        
        if self.client:
            # Use Qdrant
            qdrant_filter = None
            if collection_id:
                try:
                    try:
                        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
                    except ImportError:
                        from qdrant_client.models import Filter, FieldCondition, MatchValue  # type: ignore

                    qdrant_filter = Filter(
                        must=[
                            FieldCondition(
                                key="collection_id",
                                match=MatchValue(value=collection_id)
                            )
                        ]
                    )
                except Exception as filter_error:
                    logger.warning(f"Failed to apply collection filter: {filter_error}")

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector.tolist(),
                limit=top_k,
                query_filter=qdrant_filter
            )
            try:
                payload_collections = [r.payload.get("collection_id") for r in results[:5]]
                logger.info(
                    f"[QDRANT SEARCH] filter={collection_id} returned {len(results)} results, sample collections={payload_collections}"
                )
            except Exception as log_error:
                logger.warning(f"[QDRANT SEARCH] Failed to log payload collections: {log_error}")
            return [{"payload": r.payload, "score": r.score} for r in results]
        else:
            # Use fallback: simple cosine similarity
            import numpy as np
            logger.info(f"[SEARCH DEBUG] Total documents in memory: {len(self.documents)}")
            
            if not self.documents:
                logger.warning("[SEARCH DEBUG] No documents found in memory storage")
                return []
            
            scores = []
            for doc_id, doc_data in self.documents.items():
                try:
                    # Skip documents outside requested collection
                    if collection_id and doc_data["payload"].get("collection_id") and doc_data["payload"].get("collection_id") != collection_id:
                        continue

                    # Cosine similarity
                    doc_vector = doc_data["vector"]
                    
                    # Ensure vectors are numpy arrays
                    if not isinstance(query_vector, np.ndarray):
                        query_vector = np.array(query_vector)
                    if not isinstance(doc_vector, np.ndarray):
                        doc_vector = np.array(doc_vector)
                    
                    # Calculate cosine similarity
                    dot_product = np.dot(query_vector, doc_vector)
                    query_norm = np.linalg.norm(query_vector)
                    doc_norm = np.linalg.norm(doc_vector)
                    
                    if query_norm == 0 or doc_norm == 0:
                        similarity = 0.0
                    else:
                        similarity = dot_product / (query_norm * doc_norm)
                    
                    scores.append({
                        "payload": doc_data["payload"],
                        "score": float(similarity),
                        "id": doc_id
                    })
                except Exception as e:
                    logger.error(f"[SEARCH DEBUG] Error processing document {doc_id}: {e}")
                    continue
            
            logger.info(f"[SEARCH DEBUG] Calculated {len(scores)} similarity scores")
            
            # Sort by score and return top_k
            scores.sort(key=lambda x: x["score"], reverse=True)
            
            if scores:
                logger.info(f"[SEARCH DEBUG] Top score: {scores[0]['score']:.4f}")
                logger.info(f"[SEARCH DEBUG] Returning {min(len(scores), top_k)} results")
            
            return scores[:top_k]
