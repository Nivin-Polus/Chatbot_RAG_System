# app/core/vectorstore.py

import uuid
import logging
import json
from typing import Optional
from app.config import settings

logger = logging.getLogger("vectorstore_logger")
logging.basicConfig(level=logging.INFO)

class VectorStore:
    def __init__(self, url=settings.VECTOR_DB_URL, collection_name="kb_docs"):
        self.collection_name = collection_name
        self.url = url
        self._collection_verified = False
        self._init_client()

    def _init_client(self):
        try:
            # Import here to avoid PyO3 initialization issues during module import
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import PointStruct, Distance
            self.client = QdrantClient(url=self.url, timeout=30)
            self.PointStruct = PointStruct
            self.Distance = Distance
            # Ensure collection exists
            self._ensure_collection()
            logger.debug("Qdrant client initialized successfully")
        except Exception as e:
            logger.warning(f"Qdrant client initialization failed: {e}")
            logger.debug("Using in-memory vector storage fallback")
            self.client = None
            self._init_fallback_storage()

    def _init_fallback_storage(self):
        """Initialize in-memory vector storage as fallback"""
        self.documents = {}  # id -> {vector, payload}

    @property
    def embeddings(self):
        """Lazily initialize embeddings to avoid PyO3 issues during module import"""
        if not hasattr(self, '_embeddings_instance'):
            from app.core.embeddings import Embeddings
            self._embeddings_instance = Embeddings()
        return self._embeddings_instance
        
    def _ensure_collection(self):
        if self.client:
            if self._collection_verified:
                return

            try:
                # Check if collection exists by getting collections list
                logger.debug(f"Checking if collection {self.collection_name} exists... Instance: {id(self)}")
                collections = self.client.get_collections()
                collection_names = [col.name for col in collections.collections]
                if self.collection_name in collection_names:
                    # logger.info(f"Qdrant collection '{self.collection_name}' already exists.")
                    self._collection_verified = True
                    return
            except Exception as e:
                # If get_collections method doesn't work, try alternative approach
                logger.warning(f"[DEBUG] get_collections check failed: {e}")
                pass
            
            try:
                # Try to create collection - if it exists, this will fail with 409
                from qdrant_client.http.models import VectorParams
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=self.Distance.COSINE)
                )
                logger.debug(f"Qdrant collection '{self.collection_name}' created.")
                
                # FIX 19: Payload Indexing
                self._create_payload_indexes()
                
                self._collection_verified = True
            except Exception as create_error:
                if "already exists" in str(create_error) or "409" in str(create_error):
                    # logger.info(f"Qdrant collection '{self.collection_name}' already exists.")
                    self._collection_verified = True
                    # Try indexing anyway just in case
                    try:
                        self._create_payload_indexes()
                    except:
                        pass
                else:
                    logger.error(f"Failed to create collection: {create_error}")
                    pass

    def _create_payload_indexes(self):
        """Create indexes for frequently filtered fields (Fix 19)."""
        if not self.client: return
        try:
            fields = ["organization", "entity_type", "source_type", "file_id", "crawl_job_id", "domain"]
            for field in fields:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword"
                )
            logger.info("Payload indexes created/verified.")
        except Exception as e:
            logger.warning(f"Failed to create payload indexes: {e}")

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
            logger.debug(f"Document added to Qdrant: {metadata.get('file_name') if metadata else 'unknown'}")
        else:
            # Use fallback storage
            self.documents[doc_id] = {
                "vector": vector,
                "payload": metadata or {}
            }
            logger.debug(f"Document added to memory: {metadata.get('file_name') if metadata else 'unknown'}")
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
            logger.debug(f"Document deleted from Qdrant: {point_id}")
        else:
            if point_id in self.documents:
                del self.documents[point_id]
                logger.debug(f"Document deleted from memory: {point_id}")

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
            logger.debug(f"All chunks for file {file_id} deleted from Qdrant")
        else:
            # For fallback storage, delete all documents with matching file_id
            to_delete = []
            for doc_id, doc_data in self.documents.items():
                if doc_data["payload"].get("file_id") == file_id:
                    to_delete.append(doc_id)
            for doc_id in to_delete:
                del self.documents[doc_id]
            logger.debug(f"Deleted {len(to_delete)} chunks for file {file_id} from memory")
            return len(to_delete)

    def delete_documents_by_crawl_job_id(self, crawl_job_id: str) -> int:
        """Delete all document chunks belonging to a specific crawl job"""
        if self.client:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            # Delete all points with matching crawl_job_id in payload
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="crawl_job_id",
                            match=MatchValue(value=crawl_job_id)
                        )
                    ]
                )
            )
            logger.debug(f"All chunks for crawl job {crawl_job_id} deleted from Qdrant")
            return -1  # Qdrant doesn't return count
        else:
            # For fallback storage, delete all documents with matching crawl_job_id
            to_delete = []
            for doc_id, doc_data in self.documents.items():
                if doc_data["payload"].get("crawl_job_id") == crawl_job_id:
                    to_delete.append(doc_id)
            for doc_id in to_delete:
                del self.documents[doc_id]
            logger.debug(f"Deleted {len(to_delete)} chunks for crawl job {crawl_job_id} from memory")
            return len(to_delete)

    def get_documents_by_crawl_job_id(self, crawl_job_id: str, limit: int = 10000, allow_unsafe_scroll: bool = False) -> list:
        """Get all document chunks belonging to a specific crawl job"""
        if self.client:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            if not allow_unsafe_scroll:
                from app.core.request_context import ensure_safe_qdrant_operation
                ensure_safe_qdrant_operation("get_documents_by_crawl_job_id")

            try:
                # Scroll through all points with matching crawl_job_id
                results = []
                offset = None
                while True:
                    response = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=Filter(
                            must=[
                                FieldCondition(
                                    key="crawl_job_id",
                                    match=MatchValue(value=crawl_job_id)
                                )
                            ]
                        ),
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False
                    )
                    points, offset = response
                    if not points:
                        break
                    results.extend([{
                        "id": str(p.id),
                        "payload": p.payload
                    } for p in points])
                    if len(results) >= limit or offset is None:
                        break
                logger.debug(f"Retrieved {len(results)} chunks for crawl job {crawl_job_id} from Qdrant")
                return results[:limit]
            except Exception as e:
                logger.error(f"Failed to get documents by crawl_job_id: {e}")
                return []
        else:
            # For fallback storage
            results = []
            for doc_id, doc_data in self.documents.items():
                if doc_data["payload"].get("crawl_job_id") == crawl_job_id:
                    results.append({
                        "id": doc_id,
                        "payload": doc_data["payload"]
                    })
                    if len(results) >= limit:
                        break
            logger.debug(f"Retrieved {len(results)} chunks for crawl job {crawl_job_id} from memory")
            return results

    def iter_documents_by_crawl_job_id(self, crawl_job_id: str, batch_size: int = 100, allow_unsafe_scroll: bool = False):
        """
        Generator that yields document chunks for a crawl job in batches.
        This is memory-efficient for large exports as it doesn't accumulate all results.
        
        Yields:
            list: Batches of document dicts with 'id' and 'payload' keys
        """
        if self.client:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            if not allow_unsafe_scroll:
                from app.core.request_context import ensure_safe_qdrant_operation
                ensure_safe_qdrant_operation("iter_documents_by_crawl_job_id")
                
            try:
                offset = None
                total_yielded = 0
                while True:
                    response = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=Filter(
                            must=[
                                FieldCondition(
                                    key="crawl_job_id",
                                    match=MatchValue(value=crawl_job_id)
                                )
                            ]
                        ),
                        limit=batch_size,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False
                    )
                    points, offset = response
                    if not points:
                        break
                    
                    batch = [{
                        "id": str(p.id),
                        "payload": p.payload
                    } for p in points]
                    total_yielded += len(batch)
                    yield batch
                    
                    if offset is None:
                        break
                
                logger.debug(f"Streamed {total_yielded} chunks for crawl job {crawl_job_id} from Qdrant")
            except Exception as e:
                logger.error(f"Failed to iterate documents by crawl_job_id: {e}")
                return
        else:
            # For fallback storage - yield in batches
            batch = []
            for doc_id, doc_data in self.documents.items():
                if doc_data["payload"].get("crawl_job_id") == crawl_job_id:
                    batch.append({
                        "id": doc_id,
                        "payload": doc_data["payload"]
                    })
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
            if batch:
                yield batch
            logger.debug(f"Streamed chunks for crawl job {crawl_job_id} from memory")

    def search(self, query: str, top_k: int = 5, collection_id: Optional[str] = None, score_threshold: float = 0.0, filters: Optional[dict] = None):
        """
        Search for similar documents.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            collection_id: Optional collection filter
            score_threshold: Minimum similarity score (0.0 = no filtering)
            filters: Optional Qdrant filter dictionary (overrides collection_id if provided)
        """
        query_vector = self.embeddings.encode(query)
        
        logger.info(f"[RAG SEARCH] Query: '{query}' | top_k={top_k} | collection_id={collection_id}")
        
        if self.client:
            # Handle filter conversion
            qdrant_filter = None
            
            try:
                from qdrant_client.http import models as qmodels
                
                if filters:
                    # Convert dict filters to Qdrant model objects if necessary
                    if isinstance(filters, dict):
                        must_conditions = []
                        for m in filters.get("must", []):
                            if "range" in m:
                                must_conditions.append(qmodels.FieldCondition(key=m["key"], range=qmodels.Range(**m["range"])))
                            elif "match" in m:
                                must_conditions.append(qmodels.FieldCondition(key=m["key"], match=qmodels.MatchValue(**m["match"])))
                        
                        should_conditions = []
                        for s in filters.get("should", []):
                            if "range" in s:
                                should_conditions.append(qmodels.FieldCondition(key=s["key"], range=qmodels.Range(**s["range"])))
                            elif "match" in s:
                                should_conditions.append(qmodels.FieldCondition(key=s["key"], match=qmodels.MatchValue(**s["match"])))
                        
                        # Only create Filter if we have conditions
                        if must_conditions or should_conditions:
                            qdrant_filter = qmodels.Filter(must=must_conditions, should=should_conditions)
                            logger.info(f"[RAG SEARCH] Converted dict filters to Qdrant models")
                    else:
                        qdrant_filter = filters
                
                # If no custom filters provided, build default collection filter
                if not qdrant_filter and collection_id:
                    qdrant_filter = qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="collection_id",
                                match=qmodels.MatchValue(value=collection_id)
                            )
                        ]
                    )
                    logger.debug(f"[RAG SEARCH] Applied collection filter: {collection_id}")
            except Exception as filter_error:
                logger.error(f"Failed to build search filters: {filter_error}")
                # Fallback to no filter rather than failing
                qdrant_filter = None

            # FIX 19: Connection Resilience (Retry Logic)
            import time
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    # Log usage of custom filters for debugging
                    if qdrant_filter:
                        logger.debug(f"[RAG SEARCH] Final filter object: {qdrant_filter}")

                    results = self.client.search(
                        collection_name=self.collection_name,
                        query_vector=query_vector.tolist(),
                        limit=top_k * 4,  # Fetch significantly more for better Python-side reranking
                        query_filter=qdrant_filter
                    )
                    
                    # Enhanced logging for debugging retrieval issues
                    logger.info(f"[RAG SEARCH] Qdrant returned {len(results)} raw results")
                    
                    # Log top results with scores and text snippets
                    for i, r in enumerate(results[:5]):
                        text_snippet = r.payload.get("text", "")[:100].replace("\n", " ")
                        file_name = r.payload.get("file_name", "unknown")
                        source_type = r.payload.get("source_type", "file")
                        logger.info(f"[RAG SEARCH] Result {i+1}: score={r.score:.4f} | source={source_type} | file={file_name}")
                        logger.debug(f"[RAG SEARCH] Result {i+1} text: {text_snippet}...")
                    
                    # Apply score threshold filter
                    filtered_results = [r for r in results if r.score >= score_threshold]
                    if len(filtered_results) < len(results):
                        logger.info(f"[RAG SEARCH] Filtered {len(results) - len(filtered_results)} results below score threshold {score_threshold}")
                    
                    # Take top_k after filtering
                    final_results = filtered_results[:top_k]
                    
                    return [{"payload": r.payload, "score": r.score, "id": str(r.id)} for r in final_results]
                
                except Exception as e:
                    last_error = e
                    logger.warning(f"Qdrant search attempt {attempt+1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (2 ** attempt)) # Exponential backoff: 0.5, 1.0, 2.0
                    else:
                        logger.error(f"Qdrant search failed after {max_retries} attempts. Falling back locally.")

            # Fallback logic after all retries failed
            self.client = None
            if not hasattr(self, 'documents'):
                self._init_fallback_storage()
        
        if not self.client:
            # Use fallback: simple cosine similarity
            import numpy as np
            logger.debug(f"[SEARCH DEBUG] Total documents in memory: {len(self.documents)}")
            
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
            
            logger.debug(f"[SEARCH DEBUG] Calculated {len(scores)} similarity scores")
            
            # Sort by score and return top_k
            scores.sort(key=lambda x: x["score"], reverse=True)
            
            if scores:
                logger.debug(f"[SEARCH DEBUG] Top score: {scores[0]['score']:.4f}")
                logger.debug(f"[SEARCH DEBUG] Returning {min(len(scores), top_k)} results")
            
            return scores[:top_k]

    def get_all_unique_values(self, field: str, filter_key: str = None, filter_value: str = None, allow_unsafe_scroll: bool = False) -> list:
        """
        Get all unique values for a specific field from documents.
        Optionally filter by another key-value pair.
        """
        unique_values = set()
        
        if self.client:
             from qdrant_client.models import Filter, FieldCondition, MatchValue

             if not allow_unsafe_scroll:
                 from app.core.request_context import ensure_safe_qdrant_operation
                 ensure_safe_qdrant_operation("get_all_unique_values")
             
             scroll_filter = None
             if filter_key and filter_value:
                 scroll_filter = Filter(
                    must=[
                        FieldCondition(
                            key=filter_key,
                            match=MatchValue(value=filter_value)
                        )
                    ]
                )
             
             try:
                 offset = None
                 while True:
                     response = self.client.scroll(
                         collection_name=self.collection_name,
                         scroll_filter=scroll_filter,
                         limit=100,
                         offset=offset,
                         with_payload=True,
                         with_vectors=False
                     )
                     points, offset = response
                     if not points:
                         break
                     
                     for p in points:
                         val = p.payload.get(field)
                         if val:
                             unique_values.add(val)
                             
                     if offset is None:
                         break
             except Exception as e:
                 logger.error(f"Failed to get unique values from Qdrant: {e}")
        else:
            # Fallback
            for doc_data in self.documents.values():
                payload = doc_data["payload"]
                if filter_key and filter_value:
                    if payload.get(filter_key) != filter_value:
                        continue
                
                val = payload.get(field)
                if val:
                    unique_values.add(val)
                    
        return list(unique_values)
