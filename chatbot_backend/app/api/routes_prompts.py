# app/api/routes_prompts.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from app.core.database import get_db
from app.core.permissions import get_current_user, require_super_admin, require_admin_or_above
from app.models.user import User
from app.models.system_prompt import (
    SystemPrompt, SystemPromptCreate, SystemPromptUpdate,
    SystemPromptResponse, SystemPromptWithDetails
)
from app.models.vector_database import VectorDatabase
from app.models.website import Website
from app.models.collection import Collection, CollectionUser
import logging

router = APIRouter()


def _ensure_vector_db_for_collection(collection: Collection, db: Session) -> VectorDatabase:
    if collection.vector_db_id:
        vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == collection.vector_db_id).first()
        if vector_db:
            return vector_db

    base_name = collection.name or collection.collection_id or "Collection"
    vector_db_name = f"Vector DB - {base_name}"
    collection_name = f"collection_{collection.collection_id}_{uuid.uuid4().hex[:6]}"

    vector_db = VectorDatabase(
        name=vector_db_name,
        description=f"Auto-created for collection {base_name}",
        website_id=collection.website_id,
        collection_name=collection_name
    )
    db.add(vector_db)
    db.flush()

    collection.vector_db_id = vector_db.vector_db_id
    db.add(collection)

    return vector_db


def _ensure_default_prompt_for_collection(collection: Collection, db: Session) -> Optional[SystemPrompt]:
    existing_prompt = db.query(SystemPrompt).filter(
        SystemPrompt.collection_id == collection.collection_id
    ).first()

    if existing_prompt:
        return existing_prompt

    if not collection.website_id:
        logging.warning(f"Cannot create default prompt for collection {collection.collection_id} without website_id")
        return None

    vector_db = _ensure_vector_db_for_collection(collection, db)

    default_prompt = SystemPrompt(
        name=f"Default Prompt - {collection.name or collection.collection_id}",
        description=f"Default AI prompt for {collection.name or collection.collection_id}",
        system_prompt="You are a helpful AI assistant. Answer questions based on the provided context.",
        collection_id=collection.collection_id,
        website_id=collection.website_id,
        vector_db_id=vector_db.vector_db_id,
        is_default=True,
        is_active=True,
        model_name="claude-3-haiku-20240307",
        max_tokens=4000,
        temperature=0.7
    )

    db.add(default_prompt)
    db.commit()
    db.refresh(default_prompt)

    return default_prompt

@router.get("/", response_model=List[SystemPromptWithDetails])
async def list_prompts(
    vector_db_id: Optional[str] = None,
    website_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List system prompts with filtering based on user role"""
    try:
        query = db.query(SystemPrompt)

        if current_user.is_super_admin():
            if website_id:
                query = query.filter(SystemPrompt.website_id == website_id)
            if vector_db_id:
                query = query.filter(SystemPrompt.vector_db_id == vector_db_id)
            if collection_id:
                query = query.filter(SystemPrompt.collection_id == collection_id)
        elif current_user.is_user_admin():
            # UserAdmin can only see prompts for collections they manage
            managed_collections = db.query(Collection.collection_id).filter(
                Collection.admin_user_id == current_user.user_id
            ).subquery()
            
            query = query.filter(SystemPrompt.collection_id.in_(managed_collections))
            
            # Apply additional filters if provided
            if collection_id:
                # Verify user manages this collection
                user_manages_collection = db.query(Collection).filter(
                    Collection.collection_id == collection_id,
                    Collection.admin_user_id == current_user.user_id
                ).first()
                if user_manages_collection:
                    query = query.filter(SystemPrompt.collection_id == collection_id)
                else:
                    # User doesn't manage this collection, return empty
                    prompts = []
                    return [prompt.to_dict() for prompt in prompts]
        else:
            # Regular users can only see prompts for collections they have access to
            user_collections = db.query(CollectionUser.collection_id).filter(
                CollectionUser.user_id == current_user.user_id
            ).subquery()
            
            query = query.filter(SystemPrompt.collection_id.in_(user_collections))
            
            if collection_id:
                query = query.filter(SystemPrompt.collection_id == collection_id)

        prompts = query.all()

        if collection_id and not prompts:
            collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
            if collection:
                created_prompt = _ensure_default_prompt_for_collection(collection, db)
                if created_prompt:
                    prompts = query.all()

        # Enhance with vector database and website names (handle null values gracefully)
        result = []
        for prompt in prompts:
            try:
                vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == prompt.vector_db_id).first()
                if not vector_db:
                    vector_db = _ensure_vector_db_for_collection(db.query(Collection).filter(Collection.collection_id == prompt.collection_id).first(), db)
                if not vector_db:
                    raise HTTPException(status_code=404, detail="Vector database not found")
                website = db.query(Website).filter(Website.website_id == prompt.website_id).first()
                collection = db.query(Collection).filter(Collection.collection_id == prompt.collection_id).first() if prompt.collection_id else None

                prompt_dict = prompt.to_dict()
                prompt_dict.update({
                    "vector_db_name": vector_db.name if vector_db else "Unknown",
                    "website_name": website.name if website else "Unknown",
                    "collection_name": collection.name if collection else None
                })
                result.append(prompt_dict)
            except Exception as e:
                logging.warning(f"Error processing prompt {prompt.prompt_id}: {e}")
                # Add prompt with default values
                prompt_dict = prompt.to_dict()
                prompt_dict.update({
                    "vector_db_name": "Unknown",
                    "website_name": "Unknown"
                })
                result.append(prompt_dict)
        
        return result
        
    except Exception as e:
        logging.error(f"Error listing prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=SystemPromptResponse)
async def create_prompt(
    prompt_data: SystemPromptCreate,
    current_user: User = Depends(require_admin_or_above),
    db: Session = Depends(get_db)
):
    """Create a new system prompt"""
    try:
        collection: Optional[Collection] = None
        vector_db: Optional[VectorDatabase] = None
        website_id: Optional[str] = None

        if prompt_data.collection_id:
            collection = db.query(Collection).filter(Collection.collection_id == prompt_data.collection_id).first()
            if not collection:
                raise HTTPException(status_code=404, detail="Collection not found")

            # Check if collection already has a prompt (one prompt per collection rule)
            existing_prompt = db.query(SystemPrompt).filter(SystemPrompt.collection_id == prompt_data.collection_id).first()
            if existing_prompt:
                raise HTTPException(status_code=400, detail="Collection already has a prompt. Each collection can have only one prompt.")

            if not current_user.is_super_admin():
                if current_user.website_id != collection.website_id and collection.admin_user_id != current_user.user_id:
                    raise HTTPException(status_code=403, detail="You can only create prompts for your collections")

            website_id = collection.website_id
            if collection.vector_db_id:
                vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == collection.vector_db_id).first()

        if prompt_data.vector_db_id and not vector_db:
            vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == prompt_data.vector_db_id).first()
            if not vector_db:
                raise HTTPException(status_code=404, detail="Vector database not found")

        if vector_db and not website_id:
            website_id = vector_db.website_id

        if not website_id:
            website_id = current_user.website_id if not current_user.is_super_admin() else None

        if not current_user.is_super_admin() and website_id and current_user.website_id != website_id:
            raise HTTPException(status_code=403, detail="You can only create prompts within your website")

        if prompt_data.is_default:
            default_query = db.query(SystemPrompt).filter(SystemPrompt.is_default == True)
            if collection:
                default_query = default_query.filter(SystemPrompt.collection_id == collection.collection_id)
            elif vector_db:
                default_query = default_query.filter(SystemPrompt.vector_db_id == vector_db.vector_db_id)
            elif website_id:
                default_query = default_query.filter(SystemPrompt.website_id == website_id)
            default_query.update({"is_default": False}, synchronize_session=False)

        prompt = SystemPrompt(
            name=prompt_data.name,
            description=prompt_data.description,
            system_prompt=prompt_data.system_prompt,
            user_prompt_template=prompt_data.user_prompt_template,
            context_template=prompt_data.context_template,
            vector_db_id=vector_db.vector_db_id if vector_db else prompt_data.vector_db_id,
            website_id=website_id,
            collection_id=collection.collection_id if collection else prompt_data.collection_id,
            is_active=prompt_data.is_active,
            is_default=prompt_data.is_default,
            model_name=prompt_data.model_name,
            max_tokens=prompt_data.max_tokens,
            temperature=prompt_data.temperature
        )

        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        logging.info(
            "Created system prompt '%s' (collection=%s, vector_db=%s)",
            prompt.name,
            prompt.collection_id,
            prompt.vector_db_id
        )
        return prompt.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{prompt_id}", response_model=SystemPromptWithDetails)
async def get_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific system prompt"""
    try:
        prompt = db.query(SystemPrompt).filter(SystemPrompt.prompt_id == prompt_id).first()
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != prompt.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == prompt.vector_db_id).first()
        website = db.query(Website).filter(Website.website_id == prompt.website_id).first()
        
        result = prompt.to_dict()
        result.update({
            "vector_db_name": vector_db.name if vector_db else "Unknown",
            "website_name": website.name if website else "Unknown"
        })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{prompt_id}", response_model=SystemPromptResponse)
async def update_prompt(
    prompt_id: str,
    update_data: SystemPromptUpdate,
    current_user: User = Depends(require_admin_or_above),
    db: Session = Depends(get_db)
):
    """Update a system prompt"""
    try:
        prompt = db.query(SystemPrompt).filter(SystemPrompt.prompt_id == prompt_id).first()
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != prompt.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # If moving to a different collection
        if update_data.collection_id and update_data.collection_id != prompt.collection_id:
            collection = db.query(Collection).filter(Collection.collection_id == update_data.collection_id).first()
            if not collection:
                raise HTTPException(status_code=404, detail="Collection not found")

            if not current_user.is_super_admin():
                if current_user.website_id != collection.website_id and collection.admin_user_id != current_user.user_id:
                    raise HTTPException(status_code=403, detail="You can only manage prompts for your collections")

            prompt.collection_id = collection.collection_id
            prompt.website_id = collection.website_id

            if collection.vector_db_id:
                prompt.vector_db_id = collection.vector_db_id

        # If setting as default, unset other defaults for the same scope
        if update_data.is_default:
            default_query = db.query(SystemPrompt).filter(
                SystemPrompt.is_default == True,
                SystemPrompt.prompt_id != prompt_id
            )

            if prompt.collection_id:
                default_query = default_query.filter(SystemPrompt.collection_id == prompt.collection_id)
            elif prompt.vector_db_id:
                default_query = default_query.filter(SystemPrompt.vector_db_id == prompt.vector_db_id)
            elif prompt.website_id:
                default_query = default_query.filter(SystemPrompt.website_id == prompt.website_id)

            default_query.update({"is_default": False}, synchronize_session=False)
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(prompt, field, value)
        
        db.commit()
        db.refresh(prompt)
        
        logging.info(f"Updated system prompt: {prompt_id}")
        return prompt.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Error updating prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    current_user: User = Depends(require_admin_or_above),
    db: Session = Depends(get_db)
):
    """Delete a system prompt"""
    try:
        prompt = db.query(SystemPrompt).filter(SystemPrompt.prompt_id == prompt_id).first()
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != prompt.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Don't allow deletion of the last prompt for a vector database
        prompt_count = db.query(SystemPrompt).filter(SystemPrompt.vector_db_id == prompt.vector_db_id).count()
        if prompt_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last prompt for a vector database"
            )
        
        # If deleting default prompt, set another one as default
        if prompt.is_default:
            other_prompt = db.query(SystemPrompt).filter(
                SystemPrompt.vector_db_id == prompt.vector_db_id,
                SystemPrompt.prompt_id != prompt_id
            ).first()
            if other_prompt:
                other_prompt.is_default = True
        
        db.delete(prompt)
        db.commit()
        
        logging.info(f"Deleted system prompt: {prompt_id}")
        return {"message": "Prompt deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vector-db/{vector_db_id}/default", response_model=SystemPromptResponse)
async def get_default_prompt(
    vector_db_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the default prompt for a vector database"""
    try:
        # Verify vector database exists and user has access
        vector_db = db.query(VectorDatabase).filter(VectorDatabase.vector_db_id == vector_db_id).first()
        if not vector_db:
            raise HTTPException(status_code=404, detail="Vector database not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != vector_db.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get default prompt
        prompt = db.query(SystemPrompt).filter(
            SystemPrompt.vector_db_id == vector_db_id,
            SystemPrompt.is_default == True,
            SystemPrompt.is_active == True
        ).first()
        
        if not prompt:
            # If no default prompt, get any active prompt
            prompt = db.query(SystemPrompt).filter(
                SystemPrompt.vector_db_id == vector_db_id,
                SystemPrompt.is_active == True
            ).first()
        
        if not prompt:
            raise HTTPException(status_code=404, detail="No active prompts found for this vector database")
        
        return prompt.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting default prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{prompt_id}/test")
async def test_prompt(
    prompt_id: str,
    test_query: str,
    test_context: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test a prompt with sample query and context"""
    try:
        prompt = db.query(SystemPrompt).filter(SystemPrompt.prompt_id == prompt_id).first()
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # Check permissions
        if not current_user.is_super_admin() and current_user.website_id != prompt.website_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Format the prompt
        formatted = prompt.format_prompt(test_query, test_context)
        
        return {
            "prompt_id": prompt_id,
            "test_query": test_query,
            "test_context": test_context,
            "formatted_prompt": formatted,
            "model_config": formatted["model_config"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error testing prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
