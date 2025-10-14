# app/api/routes_vector_databases.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.permissions import get_current_user, require_super_admin, require_admin_or_above
from app.models.user import User
from app.models.vector_database import (
    VectorDatabase, VectorDatabaseCreate, VectorDatabaseUpdate, 
    VectorDatabaseResponse, VectorDatabaseWithStats
)
from app.models.website import Website
from app.models.system_prompt import SystemPrompt
import logging

router = APIRouter()

@router.get("/", response_model=List[VectorDatabaseWithStats])
async def list_vector_databases(
    website_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List vector databases with filtering based on user role"""
    try:
        query = db.query(VectorDatabase)
        
        if current_user.is_super_admin():
            # Super admin can see all vector databases
            if website_id:
                query = query.filter(VectorDatabase.website_id == website_id)
        elif current_user.is_user_admin():
            # User admin can only see their website's vector databases
            query = query.filter(VectorDatabase.website_id == current_user.website_id)
        else:
            # Regular users can only see vector databases they have access to
            # This would need to be implemented based on file access permissions
            query = query.filter(VectorDatabase.website_id == current_user.website_id)
        
        vector_dbs = query.all()
        
        # Enhance with stats and website names
        result = []
        for vdb in vector_dbs:
            website = db.query(Website).filter(Website.website_id == vdb.website_id).first()
            prompt_count = db.query(SystemPrompt).filter(SystemPrompt.vector_db_id == vdb.vector_db_id).count()
            
            vdb_dict = vdb.to_dict()
            vdb_dict.update({
                "stats": vdb.get_stats(db),
                "website_name": website.name if website else "Unknown",
                "prompt_count": prompt_count
            })
            result.append(vdb_dict)
        
        return result
        
    except Exception as e:
        logging.error(f"Error listing vector databases: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=VectorDatabaseResponse)
async def create_vector_database(
    vector_db_data: VectorDatabaseCreate,
    current_user: User = Depends(require_admin_or_above),
    db: Session = Depends(get_db)
):
    """Create a new vector database"""
    try:
        # Check if user can create in this website
        if not current_user.is_super_admin() and current_user.website_id != vector_db_data.website_id:
            raise HTTPException(
                status_code=403,
                detail="You can only create vector databases in your own website"
            )
        
        # Verify website exists
        website = db.query(Website).filter(Website.website_id == vector_db_data.website_id).first()
        if not website:
            raise HTTPException(status_code=404, detail="Website not found")
        
        # Generate unique collection name
        collection_name = f"vdb_{vector_db_data.website_id[:8]}_{vector_db_data.name.lower().replace(' ', '_')}"
        
        # Check if collection name already exists
        existing = db.query(VectorDatabase).filter(VectorDatabase.collection_name == collection_name).first()
        if existing:
            # Add suffix to make it unique
            counter = 1
            while existing:
                new_collection_name = f"{collection_name}_{counter}"
                existing = db.query(VectorDatabase).filter(VectorDatabase.collection_name == new_collection_name).first()
                counter += 1
            collection_name = new_collection_name
        
        # Create vector database
        vector_db = VectorDatabase(
            name=vector_db_data.name,
            description=vector_db_data.description,
            website_id=vector_db_data.website_id,
            collection_name=collection_name,
            web_link=vector_db_data.web_link,
            embedding_model=vector_db_data.embedding_model,
            chunk_size=vector_db_data.chunk_size,
            chunk_overlap=vector_db_data.chunk_overlap
        )
        
        db.add(vector_db)
        db.commit()
        db.refresh(vector_db)
        
        # Create default prompt for this vector database
        default_prompt = SystemPrompt(
            name=f"Default Prompt for {vector_db_data.name}",
            description="Default system prompt for this vector database",
            system_prompt="""You are a helpful AI assistant. Use the provided context to answer user questions accurately and concisely. 

Guidelines:
- Base your answers on the provided context
- If the context doesn't contain relevant information, say so clearly
- Be precise and factual
- Always cite your sources when possible

Context will be provided below:""",
            user_prompt_template="""Based on the following context, please answer the user's question:

Context:
{context}

User Question: {query}

Please provide a comprehensive answer based on the context above. If the context doesn't contain enough information to answer the question, please state that clearly.""",
            vector_db_id=vector_db.vector_db_id,
            website_id=vector_db_data.website_id,
            is_default=True
        )
        
        db.add(default_prompt)
        db.commit()
        
        logging.info(f"Created vector database: {vector_db.name} with collection: {collection_name}")
        return vector_db.to_dict()
        
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating vector database: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{vector_db_id}", response_model=VectorDatabaseWithStats)
async def get_vector_database(
    vector_db_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific vector database with stats"""
    try:
        vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == vector_db_id).first()
        if not vector_db:
            raise HTTPException(status_code=404, detail="Vector database not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != vector_db.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        website = db.query(Website).filter(Website.website_id == vector_db.website_id).first()
        prompt_count = db.query(SystemPrompt).filter(SystemPrompt.vector_db_id == vector_db_id).count()
        
        result = vector_db.to_dict()
        result.update({
            "stats": vector_db.get_stats(db),
            "website_name": website.name if website else "Unknown",
            "prompt_count": prompt_count
        })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting vector database: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{vector_db_id}", response_model=VectorDatabaseResponse)
async def update_vector_database(
    vector_db_id: str,
    update_data: VectorDatabaseUpdate,
    current_user: User = Depends(require_admin_or_above),
    db: Session = Depends(get_db)
):
    """Update a vector database"""
    try:
        vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == vector_db_id).first()
        if not vector_db:
            raise HTTPException(status_code=404, detail="Vector database not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != vector_db.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(vector_db, field, value)
        
        db.commit()
        db.refresh(vector_db)
        
        logging.info(f"Updated vector database: {vector_db_id}")
        return vector_db.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Error updating vector database: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{vector_db_id}")
async def delete_vector_database(
    vector_db_id: str,
    current_user: User = Depends(require_admin_or_above),
    db: Session = Depends(get_db)
):
    """Delete a vector database and all associated data"""
    try:
        vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == vector_db_id).first()
        if not vector_db:
            raise HTTPException(status_code=404, detail="Vector database not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != vector_db.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete associated prompts
        db.query(SystemPrompt).filter(SystemPrompt.vector_db_id == vector_db_id).delete()
        
        # Update files to remove vector_db_id reference
        from app.models.file_metadata import FileMetadata
        db.query(FileMetadata).filter(FileMetadata.vector_db_id == vector_db_id).update(
            {"vector_db_id": None, "vector_indexed": False}
        )
        
        # Delete the vector database record
        db.delete(vector_db)
        db.commit()
        
        # Delete actual vector data from Qdrant
        try:
            from app.core.vector_singleton import get_vector_store
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            vector_store = get_vector_store()
            
            if vector_store.client:
                # Delete all points associated with this vector_db_id
                deleted_count = vector_store.client.delete(
                    collection_name=vector_store.collection_name,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="vector_db_id",
                                match=MatchValue(value=vector_db_id)
                            )
                        ]
                    )
                )
                logging.info(f"Deleted vector data for vector_db_id: {vector_db_id}")
            else:
                # Fallback: delete from in-memory storage
                to_delete = [
                    doc_id for doc_id, doc_data in vector_store.documents.items()
                    if doc_data.get("payload", {}).get("vector_db_id") == vector_db_id
                ]
                for doc_id in to_delete:
                    del vector_store.documents[doc_id]
                logging.info(f"Deleted {len(to_delete)} vectors from memory for vector_db_id: {vector_db_id}")
                
        except Exception as vector_error:
            logging.warning(f"Failed to delete vector data for {vector_db_id}: {vector_error}")
            # Don't fail the entire operation if vector cleanup fails
        
        logging.info(f"Deleted vector database: {vector_db_id}")
        return {"message": "Vector database and associated vectors deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting vector database: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{vector_db_id}/stats")
async def get_vector_database_stats(
    vector_db_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed statistics for a vector database"""
    try:
        vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == vector_db_id).first()
        if not vector_db:
            raise HTTPException(status_code=404, detail="Vector database not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != vector_db.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return vector_db.get_stats(db)
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting vector database stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
