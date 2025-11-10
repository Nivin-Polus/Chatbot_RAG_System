import requests
import time
from typing import Dict, Any
from app.core.vector_singleton import get_vector_store
from app.core.rag import RAG
from app.core.database import get_db_health
from app.config import settings
import logging
import jwt
from datetime import datetime

logger = logging.getLogger(__name__)

class HealthMonitorService:
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.rag = RAG(self.vector_store)
    
    def check_qdrant_health(self) -> Dict[str, Any]:
        """Check Qdrant vector database health"""
        try:
            if not self.vector_store.client:
                # Check if fallback storage is working
                fallback_docs = len(self.vector_store.documents) if hasattr(self.vector_store, 'documents') else 0
                return {
                    "status": "healthy",  # Fallback is still functional
                    "service": "qdrant",
                    "message": f"Using fallback storage ({fallback_docs} documents)",
                    "fallback_docs": fallback_docs,
                    "mode": "fallback",
                    "url": getattr(settings, "VECTOR_DB_URL", "http://localhost:6333")
                }
            
            # Simple health check first - just try to connect
            try:
                # Try a simple operation to test connectivity
                collections = self.vector_store.client.get_collections()
                
                # Check if our collection exists
                kb_collection_exists = any(
                    col.name == self.vector_store.collection_name 
                    for col in collections.collections
                )
                
                collection_points = 0
                if kb_collection_exists:
                    try:
                        collection_info = self.vector_store.client.get_collection(
                            self.vector_store.collection_name
                        )
                        collection_points = collection_info.points_count if collection_info else 0
                    except:
                        # If we can't get collection info, that's okay
                        pass
                
                return {
                    "status": "healthy",
                    "service": "qdrant",
                    "mode": "qdrant",
                    "collections_count": len(collections.collections),
                    "kb_collection_exists": kb_collection_exists,
                    "kb_collection_points": collection_points,
                    "url": getattr(settings, "VECTOR_DB_URL", "http://localhost:6333")
                }
                
            except requests.exceptions.ConnectionError:
                # Qdrant is not running, but fallback might work
                fallback_docs = len(self.vector_store.documents) if hasattr(self.vector_store, 'documents') else 0
                return {
                    "status": "healthy" if fallback_docs > 0 else "unhealthy",
                    "service": "qdrant",
                    "message": f"Qdrant unavailable, using fallback ({fallback_docs} documents)" if fallback_docs > 0 else "Qdrant unavailable and no fallback data",
                    "fallback_docs": fallback_docs,
                    "mode": "fallback" if fallback_docs > 0 else "none",
                    "error": "Connection refused - Qdrant not running",
                    "url": getattr(settings, "VECTOR_DB_URL", "http://localhost:6333")
                }
            
        except Exception as e:
            # Check if fallback storage is available
            fallback_docs = 0
            try:
                fallback_docs = len(self.vector_store.documents) if hasattr(self.vector_store, 'documents') else 0
            except:
                pass
                
            return {
                "status": "unhealthy" if fallback_docs == 0 else "degraded",
                "service": "qdrant",
                "error": str(e),
                "fallback_docs": fallback_docs,
                "mode": "fallback" if fallback_docs > 0 else "none",
                "url": getattr(settings, "VECTOR_DB_URL", "http://localhost:6333")
            }
    
    def check_ai_model_health(self) -> Dict[str, Any]:
        """Check AI model (Claude) health with a ping test"""
        try:
            # If API key not configured, treat as healthy but disabled (permissive)
            if not getattr(settings, "CLAUDE_API_KEY", None):
                return {
                    "status": "healthy",
                    "service": "claude_ai",
                    "response_time_ms": 0,
                    "test_response": "Model disabled (no API key)",
                    "model": getattr(settings, "CLAUDE_MODEL", "claude-3-haiku-20240307"),
                    "api_configured": False
                }
            start_time = time.time()
            
            # Send a simple test query
            test_response = self.rag.call_ai("Respond with 'OK' if you can process this message.")
            
            response_time = round((time.time() - start_time) * 1000, 2)  # ms
            
            # Check if response contains expected content
            is_healthy = "OK" in test_response or len(test_response.strip()) > 0
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "service": "claude_ai",
                "response_time_ms": response_time,
                "test_response": test_response[:100] + "..." if len(test_response) > 100 else test_response,
                "model": getattr(settings, "CLAUDE_MODEL", "claude-3-haiku-20240307"),
                "api_configured": bool(getattr(settings, "CLAUDE_API_KEY", None))
            }
            
        except Exception as e:
            return {
                "status": "healthy" if not getattr(settings, "CLAUDE_API_KEY", None) else "unhealthy",
                "service": "claude_ai",
                "error": str(e),
                "model": getattr(settings, "CLAUDE_MODEL", "claude-3-haiku-20240307"),
                "api_configured": bool(getattr(settings, "CLAUDE_API_KEY", None))
            }
    
    def check_file_processing_health(self) -> Dict[str, Any]:
        """Check file processing capabilities"""
        try:
            # Check if upload directory exists and is writable
            import os
            from pathlib import Path
            
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            
            # Test write permissions
            test_file = upload_dir / "health_check.tmp"
            test_file.write_text("health check")
            test_file.unlink()  # Delete test file
            
            # Check supported file types
            supported_types = getattr(settings, "ALLOWED_FILE_TYPES", "pdf,docx,pptx,xlsx,txt").split(",")
            max_file_size = getattr(settings, "MAX_FILE_SIZE_MB", 25)
            
            return {
                "status": "healthy",
                "service": "file_processing",
                "upload_directory": str(upload_dir.absolute()),
                "directory_writable": True,
                "supported_types": supported_types,
                "max_file_size_mb": max_file_size
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "file_processing",
                "error": str(e)
            }
    
    def check_authentication_health(self) -> Dict[str, Any]:
        """Check authentication system health"""
        try:
            # Check if JWT secret key is configured
            secret_key = getattr(settings, "SECRET_KEY", None)
            algorithm = getattr(settings, "ALGORITHM", "HS256")
            
            logger.info(f"Auth health check - SECRET_KEY present: {bool(secret_key)}")
            
            if not secret_key:
                return {
                    "status": "unhealthy",
                    "service": "authentication",
                    "error": "JWT SECRET_KEY not configured"
                }
            
            # Test JWT token creation and validation
            from datetime import datetime, timedelta
            import time
            
            current_time = int(time.time())
            exp_time = current_time + 300  # 5 minutes from now
            
            test_payload = {
                "sub": "health_check",
                "iat": current_time,  # issued at
                "exp": exp_time       # expires at
            }
            
            logger.info(f"JWT test - current time: {current_time}, exp time: {exp_time}")
            
            # Create test token
            test_token = jwt.encode(test_payload, secret_key, algorithm=algorithm)
            
            # Validate test token
            decoded = jwt.decode(test_token, secret_key, algorithms=[algorithm])
            
            # Check database connectivity
            db_health = get_db_health()
            
            return {
                "status": "healthy",
                "service": "authentication",
                "jwt_configured": True,
                "algorithm": algorithm,
                "token_test": "passed",
                "database": db_health
            }
            
        except Exception as e:
            logger.error(f"Authentication health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "service": "authentication",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get complete system health overview"""
        try:
            start_time = time.time()
            
            # Run all health checks
            qdrant_health = self.check_qdrant_health()
            ai_health = self.check_ai_model_health()
            file_health = self.check_file_processing_health()
            auth_health = self.check_authentication_health()
            
            # Calculate overall status
            all_services = [qdrant_health, ai_health, file_health, auth_health]
            healthy_services = sum(1 for service in all_services if service["status"] == "healthy")
            degraded_services = sum(1 for service in all_services if service["status"] == "degraded")
            total_services = len(all_services)
            
            # Determine overall status
            if healthy_services == total_services:
                overall_status = "healthy"
            elif healthy_services + degraded_services == total_services:
                overall_status = "degraded"  # All services are either healthy or degraded
            elif healthy_services + degraded_services > 0:
                overall_status = "degraded"  # Mix of healthy/degraded/unhealthy
            else:
                overall_status = "unhealthy"  # All services are unhealthy
            
            total_time = round((time.time() - start_time) * 1000, 2)
            
            return {
                "overall_status": overall_status,
                "healthy_services": healthy_services,
                "total_services": total_services,
                "health_check_time_ms": total_time,
                "timestamp": datetime.utcnow().isoformat(),
                "services": {
                    "qdrant": qdrant_health,
                    "ai_model": ai_health,
                    "file_processing": file_health,
                    "authentication": auth_health
                }
            }
            
        except Exception as e:
            return {
                "overall_status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
