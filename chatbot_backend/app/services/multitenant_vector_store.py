# app/services/multitenant_vector_store.py

import logging
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, VectorParams, Distance
import uuid
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger(__name__)

class MultiTenantVectorStore:
    """
    Multi-tenant vector store using Qdrant with metadata filtering.
    Uses one big collection with metadata filters for department isolation.
    """
    
    def __init__(self):
        self.client = None
        self.collection_name = "multitenant_documents"
        self.vector_size = 384  # sentence-transformers/all-MiniLM-L6-v2 default
        self.embedding_model = None
        self._initialize_client()
        self._initialize_embedding_model()
    
    def _initialize_client(self):
        """Initialize Qdrant client"""
        try:
            self.client = QdrantClient(url=settings.VECTOR_DB_URL)
            self._ensure_collection()
            logger.info("✅ Multi-tenant vector store initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize vector store: {e}")
            raise
    
    def _initialize_embedding_model(self):
        """Initialize sentence transformer model"""
        try:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Embedding model initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize embedding model: {e}")
            raise
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        try:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"❌ Failed to generate embedding: {e}")
            raise
    
    def _ensure_collection(self):
        """Ensure the main collection exists"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"📋 Creating collection: {self.collection_name}")
                
                # Create collection with vector configuration
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                
                # Create indexes for efficient filtering
                self._create_indexes()
                
                logger.info(f"✅ Collection {self.collection_name} created successfully")
            else:
                logger.info(f"📋 Collection {self.collection_name} already exists")
                
        except Exception as e:
            logger.error(f"❌ Failed to ensure collection: {e}")
            raise
    
    def _create_indexes(self):
        """Create indexes for efficient metadata filtering"""
        try:
            # Create index for website_id (most important for tenant isolation)
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="website_id",
                field_schema=models.KeywordIndexParams()
            )
            
            # Create index for file_id
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="file_id",
                field_schema=models.KeywordIndexParams()
            )
            
            # Create index for uploader_id
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="uploader_id",
                field_schema=models.KeywordIndexParams()
            )
            
            # Create index for is_public
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="is_public",
                field_schema=models.KeywordIndexParams()
            )
            
            logger.info("✅ Metadata indexes created successfully")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to create some indexes: {e}")
    
    def add_documents(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadata_list: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Add documents to the vector store with metadata for multi-tenant filtering
        
        Args:
            texts: List of document texts
            embeddings: List of embedding vectors
            metadata_list: List of metadata dicts containing website_id, file_id, etc.
            
        Returns:
            List of point IDs
        """
        try:
            if len(texts) != len(embeddings) != len(metadata_list):
                raise ValueError("texts, embeddings, and metadata_list must have the same length")
            
            points = []
            point_ids = []
            
            for i, (text, embedding, metadata) in enumerate(zip(texts, embeddings, metadata_list)):
                point_id = str(uuid.uuid4())
                point_ids.append(point_id)
                
                # Ensure required metadata fields
                if "file_id" not in metadata:
                    raise ValueError("file_id is required in metadata")
                
                # Add text content to metadata
                full_metadata = {
                    **metadata,
                    "text": text,
                    "chunk_index": i
                }
                
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=full_metadata
                    )
                )
            
            # Upload points to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"✅ Added {len(points)} documents to vector store")
            return point_ids
            
        except Exception as e:
            logger.error(f"❌ Failed to add documents: {e}")
            raise
    
    def search_documents(
        self,
        query_embedding: List[float],
        website_id: Optional[str],
        accessible_file_ids: List[str],
        limit: int = 10,
        score_threshold: float = 0.7,
        additional_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents with multi-tenant filtering
        
        Args:
            query_embedding: Query vector
            website_id: Website/department ID for tenant isolation
            accessible_file_ids: List of file IDs the user can access
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            additional_filters: Additional metadata filters
            
            List of search results with metadata
        """
        try:
            # Build filter conditions
            filter_conditions: List[FieldCondition] = []

            if website_id:
                filter_conditions.append(
                    FieldCondition(
                        key="website_id",
                        match=MatchValue(value=website_id)
                    )
                )

            # File access control: must be in accessible_file_ids
            if accessible_file_ids:
                filter_conditions.append(
                    FieldCondition(
                        key="file_id",
                        match=MatchValue(value=accessible_file_ids)
                    )
                )
            else:
                # If no accessible files, return empty results
                logger.warning(f"User has no accessible files in website {website_id}")
                return []

            # Add additional filters if provided
            if additional_filters:
                for key, value in additional_filters.items():
                    filter_conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )

            # Create filter object (only if we have conditions)
            search_filter = Filter(must=filter_conditions) if filter_conditions else None

            # Perform search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "text": result.payload.get("text", ""),
                    "metadata": {
                        k: v for k, v in result.payload.items() 
                        if k not in ["text"]
                    }
                })
            
            logger.info(f"🔍 Found {len(results)} documents for website {website_id}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to search documents: {e}")
            raise
    
    def delete_documents_by_file_id(self, file_id: str, website_id: Optional[str] = None) -> bool:
        """
        Delete all documents for a specific file with tenant isolation
        
        Args:
            file_id: File ID to delete
            website_id: Website ID for additional security
            
        Returns:
            True if successful
        """
        try:
            # Create filter for file deletion with tenant isolation
            conditions = [
                FieldCondition(
                    key="file_id",
                    match=MatchValue(value=file_id)
                )
            ]
            if website_id:
                conditions.append(
                    FieldCondition(
                        key="website_id",
                        match=MatchValue(value=website_id)
                    )
                )

            delete_filter = Filter(must=conditions)
            
            # Delete points matching the filter
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=delete_filter)
            )
            
            logger.info(f"🗑️ Deleted documents for file {file_id} in website {website_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete documents for file {file_id}: {e}")
            return False
    
    def delete_documents_by_website_id(self, website_id: str) -> bool:
        """
        Delete all documents for a website (when deleting a department)
        
        Args:
            website_id: Website ID to delete all documents for
            
        Returns:
            True if successful
        """
        try:
            delete_filter = Filter(
                must=[
                    FieldCondition(
                        key="website_id",
                        match=MatchValue(value=website_id)
                    )
                ]
            )
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=delete_filter)
            )
            
            logger.info(f"🗑️ Deleted all documents for website {website_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete documents for website {website_id}: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                "collection_name": self.collection_name,
                "points_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "status": collection_info.status.value if collection_info.status else "unknown"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get collection stats: {e}")
            return {"error": str(e)}
    
    def get_website_stats(self, website_id: str) -> Dict[str, Any]:
        """Get statistics for a specific website"""
        try:
            # Count documents for this website
            search_result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="website_id",
                            match=MatchValue(value=website_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=False
            )
            
            # Get total count (this is a simplified approach)
            # For large datasets, you might want to use aggregation
            total_count = len(search_result[0]) if search_result[0] else 0
            
            return {
                "website_id": website_id,
                "document_count": total_count,
                "collection_name": self.collection_name
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get website stats: {e}")
            return {"error": str(e)}

# Singleton instance
_vector_store_instance = None

def get_multitenant_vector_store() -> MultiTenantVectorStore:
    """Get singleton instance of multi-tenant vector store"""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = MultiTenantVectorStore()
    return _vector_store_instance
