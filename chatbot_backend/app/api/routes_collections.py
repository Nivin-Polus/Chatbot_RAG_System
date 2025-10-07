"""
Collections API routes for the collection-based RAG system.
Handles CRUD operations for collections and collection-user assignments.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid
import logging
from urllib.parse import urlparse

from ..core.database import get_db
from ..models.collection import Collection, CollectionUser, CollectionWebsite
from ..models.user import User
from ..models.system_prompt import SystemPrompt
from ..models.website import Website
from ..models.vector_database import VectorDatabase
from ..core.permissions import get_current_user, require_super_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collections", tags=["collections"])


# Pydantic models
class CollectionCreate(BaseModel):
    name: str
    admin_username: str
    admin_password: str
    description: Optional[str] = None
    admin_email: Optional[str] = None
    website_id: Optional[str] = None
    website_url: Optional[str] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    website_url: Optional[str] = None
    is_active: Optional[bool] = None
    admin_user_id: Optional[str] = None


class CollectionWebsiteCreate(BaseModel):
    url: str


class CollectionWebsiteResponse(BaseModel):
    id: int
    collection_id: str
    url: str
    normalized_url: str
    created_at: str
    created_by: Optional[str]

    class Config:
        from_attributes = True


class CollectionSummary(BaseModel):
    collection_id: str
    name: str
    description: Optional[str]
    is_active: bool


class CollectionResponse(BaseModel):
    collection_id: str
    name: str
    description: Optional[str]
    website_url: Optional[str]
    admin_email: Optional[str]
    is_active: bool
    user_count: int
    prompt_count: int
    file_count: int
    created_at: str
    updated_at: Optional[str]
    website_urls: List[CollectionWebsiteResponse] = []

    class Config:
        from_attributes = True


class UserAssignment(BaseModel):
    user_id: str
    role: str = "user"
    can_upload: bool = True
    can_download: bool = True
    can_delete: bool = False


def _get_accessible_collections(current_user: User, db: Session):
    if current_user.role == "super_admin":
        return db.query(Collection).all()

    if current_user.role == "user_admin":
        return db.query(Collection).filter(
            Collection.admin_user_id == current_user.user_id
        ).all()

    user_collections = db.query(CollectionUser).filter(
        CollectionUser.user_id == current_user.user_id
    ).all()
    collection_ids = [uc.collection_id for uc in user_collections]
    if not collection_ids:
        return []
    return db.query(Collection).filter(
        Collection.collection_id.in_(collection_ids)
    ).all()


@router.get("/", response_model=List[CollectionResponse])
async def get_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all collections (super admin) or user's collections (admin/user)"""
    try:
        collections = _get_accessible_collections(current_user, db)
        return [_collection_to_response(c) for c in collections]
    except Exception as e:
        logger.error(f"Error getting collections: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve collections")


@router.get("/summary", response_model=List[CollectionSummary])
async def get_collection_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lightweight list of collections available to the current user."""
    try:
        collections = _get_accessible_collections(current_user, db)
        return [
            CollectionSummary(
                collection_id=collection.collection_id,
                name=collection.name,
                description=collection.description,
                is_active=collection.is_active,
            )
            for collection in collections
        ]
    except Exception as e:
        logger.error(f"Error getting collection summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve collection summary")


@router.post("/", response_model=CollectionResponse)
async def create_collection(
    collection_data: CollectionCreate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Create a new collection (super admin only)"""
    try:
        # Generate unique collection ID
        collection_id = f"col_{uuid.uuid4().hex[:8]}"

        # Determine target website (ensure one always exists)
        target_website: Optional[Website] = None
        target_website_id: Optional[str] = None

        if collection_data.website_id:
            target_website = db.query(Website).filter(Website.website_id == collection_data.website_id).first()
            if not target_website:
                raise HTTPException(status_code=404, detail="Website not found")
            target_website_id = target_website.website_id
        elif collection_data.website_url:
            parsed_url = urlparse(collection_data.website_url)
            domain = (parsed_url.netloc or parsed_url.path).lower().strip()
            if domain:
                target_website = db.query(Website).filter(Website.domain == domain).first()
                if target_website:
                    target_website_id = target_website.website_id
        
        # If still no website, use or create default
        if not target_website_id:
            default_site = db.query(Website).filter(Website.domain == "default.local").first()
            if not default_site:
                default_site = Website(
                    name="Default Organization",
                    domain="default.local",
                    is_active=True
                )
                db.add(default_site)
                db.flush()
            target_website_id = default_site.website_id
            target_website = default_site
            logger.info(f"Using default website for collection: {target_website_id}")

        # Check if admin user exists by username first, then by email if provided
        admin_user = db.query(User).filter(User.username == collection_data.admin_username).first()
        if not admin_user and collection_data.admin_email:
            admin_user = db.query(User).filter(User.email == collection_data.admin_email).first()

        if not admin_user:
            from ..core.auth import get_password_hash
            admin_user = User(
                username=collection_data.admin_username,
                email=collection_data.admin_email,
                password_hash=get_password_hash(collection_data.admin_password),
                full_name=collection_data.admin_username,
                role="user_admin",
                is_active=True,
                website_id=target_website_id
            )
            db.add(admin_user)
            db.flush()
        else:
            updated = False
            if collection_data.admin_password:
                from ..core.auth import get_password_hash
                admin_user.password_hash = get_password_hash(collection_data.admin_password)
                updated = True
            if target_website_id and admin_user.website_id != target_website_id:
                admin_user.website_id = target_website_id
                updated = True
            if admin_user.role != "user_admin" and not admin_user.is_super_admin():
                admin_user.role = "user_admin"
                updated = True
            # Ensure user is active when assigned as collection admin
            if not admin_user.is_active:
                admin_user.is_active = True
                updated = True
            if updated:
                db.add(admin_user)

        # Ensure admin user has website_id aligned
        if target_website_id and admin_user.website_id != target_website_id:
            admin_user.website_id = target_website_id
            db.add(admin_user)
            logger.info(f"Aligned admin user website_id to collection: {target_website_id}")

        # Create collection
        collection = Collection(
            collection_id=collection_id,
            name=collection_data.name,
            description=collection_data.description,
            website_url=collection_data.website_url,
            website_id=target_website_id,
            admin_user_id=admin_user.user_id,
            admin_email=collection_data.admin_email,
            is_active=True
        )
        db.add(collection)

        # Create dedicated vector database for this collection
        vector_db_name = f"Vector DB - {collection_data.name}"
        collection_name = f"collection_{collection_id}"
        existing_vdb = db.query(VectorDatabase).filter(VectorDatabase.collection_name == collection_name).first()
        counter = 1
        while existing_vdb:
            collection_name_candidate = f"{collection_name}_{counter}"
            existing_vdb = db.query(VectorDatabase).filter(VectorDatabase.collection_name == collection_name_candidate).first()
            if not existing_vdb:
                collection_name = collection_name_candidate
            counter += 1

        vector_db = VectorDatabase(
            name=vector_db_name,
            description=f"Auto-created for collection {collection_data.name}",
            website_id=target_website_id,
            collection_name=collection_name
        )
        db.add(vector_db)
        db.flush()

        collection.vector_db_id = vector_db.vector_db_id

        # Assign admin to collection
        collection_user = CollectionUser(
            collection_id=collection_id,
            user_id=admin_user.user_id,
            role="admin",
            can_upload=True,
            can_download=True,
            can_delete=True,
            assigned_by=current_user.user_id
        )
        db.add(collection_user)

        # Create default prompt for collection
        default_prompt = SystemPrompt(
            name=f"Default Prompt - {collection_data.name}",
            description=f"Default AI prompt for {collection_data.name} collection",
            system_prompt="You are a helpful AI assistant. Answer questions based on the provided context.",
            collection_id=collection_id,
            website_id=target_website_id,
            vector_db_id=vector_db.vector_db_id,
            is_default=True,
            is_active=True,
            model_name="claude-3-haiku-20240307",
            max_tokens=4000,
            temperature=0.7
        )
        db.add(default_prompt)

        db.commit()
        db.refresh(collection)

        logger.info(f"Created collection {collection_id} with admin {admin_user.email}")

        return _collection_to_response(collection)

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to create collection")


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific collection"""
    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Check permissions
    if current_user.role != "super_admin" and collection.admin_user_id != current_user.user_id:
        # Check if user is assigned to this collection
        user_assignment = db.query(CollectionUser).filter(
            CollectionUser.collection_id == collection_id,
            CollectionUser.user_id == current_user.user_id
        ).first()
        
        if not user_assignment:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return _collection_to_response(collection)


def _collection_to_response(collection: Collection) -> CollectionResponse:
    return CollectionResponse(
        collection_id=collection.collection_id,
        name=collection.name,
        description=collection.description,
        website_url=collection.website_url,
        admin_email=collection.admin_email,
        is_active=collection.is_active,
        user_count=collection.user_count,
        prompt_count=collection.prompt_count,
        file_count=collection.file_count,
        created_at=collection.created_at.isoformat() if collection.created_at else "",
        updated_at=collection.updated_at.isoformat() if collection.updated_at else None,
        website_urls=[
            CollectionWebsiteResponse(
                id=wm.id,
                collection_id=wm.collection_id,
                url=wm.url,
                normalized_url=wm.normalized_url,
                created_at=wm.created_at.isoformat() if wm.created_at else "",
                created_by=wm.created_by
            )
            for wm in collection.website_mappings
        ]
    )


def _normalize_url(raw_url: str) -> str:
    if not raw_url:
        return ""

    candidate = raw_url.strip()
    if not candidate:
        return ""

    parsed = urlparse(candidate)
    if not parsed.scheme:
        parsed = urlparse(f"https://{candidate}")

    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    if not netloc:
        netloc = parsed.path.lower().rstrip("/")
        path = ""

    normalized = netloc
    if path:
        normalized = f"{normalized}{path}"

    return normalized


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    collection_data: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if current_user.role != "super_admin" and collection.admin_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        if collection_data.name is not None:
            collection.name = collection_data.name
        if collection_data.description is not None:
            collection.description = collection_data.description
        if collection_data.website_url is not None:
            collection.website_url = collection_data.website_url
        if collection_data.is_active is not None:
            collection.is_active = collection_data.is_active
        if collection_data.admin_user_id is not None:
            collection.admin_user_id = collection_data.admin_user_id

        db.commit()
        db.refresh(collection)

        return _collection_to_response(collection)

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update collection")


@router.get("/{collection_id}/websites", response_model=List[CollectionWebsiteResponse])
async def list_collection_websites(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if current_user.role != "super_admin" and collection.admin_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return [
        CollectionWebsiteResponse(
            id=wm.id,
            collection_id=wm.collection_id,
            url=wm.url,
            normalized_url=wm.normalized_url,
            created_at=wm.created_at.isoformat() if wm.created_at else "",
            created_by=wm.created_by
        )
        for wm in collection.website_mappings
    ]


@router.post("/{collection_id}/websites", response_model=CollectionWebsiteResponse, status_code=status.HTTP_201_CREATED)
async def add_collection_website(
    collection_id: str,
    website_data: CollectionWebsiteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if current_user.role != "super_admin" and collection.admin_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    normalized = _normalize_url(website_data.url)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid URL")

    existing = db.query(CollectionWebsite).filter(
        CollectionWebsite.collection_id == collection_id,
        CollectionWebsite.normalized_url == normalized
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="URL already mapped to collection")

    mapping = CollectionWebsite(
        collection_id=collection_id,
        url=website_data.url.strip(),
        normalized_url=normalized,
        created_by=current_user.user_id
    )

    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return CollectionWebsiteResponse(
        id=mapping.id,
        collection_id=mapping.collection_id,
        url=mapping.url,
        normalized_url=mapping.normalized_url,
        created_at=mapping.created_at.isoformat() if mapping.created_at else "",
        created_by=mapping.created_by
    )


@router.delete("/{collection_id}/websites/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collection_website(
    collection_id: str,
    mapping_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if current_user.role != "super_admin" and collection.admin_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    mapping = db.query(CollectionWebsite).filter(
        CollectionWebsite.id == mapping_id,
        CollectionWebsite.collection_id == collection_id
    ).first()

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    db.delete(mapping)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Delete a collection (super admin only)"""
    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    try:
        # Delete related records
        db.query(CollectionUser).filter(CollectionUser.collection_id == collection_id).delete()
        db.query(SystemPrompt).filter(SystemPrompt.collection_id == collection_id).delete()
        
        # Delete collection
        db.delete(collection)
        db.commit()
        
        logger.info(f"Deleted collection {collection_id}")
        return {"message": "Collection deleted successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting collection {collection_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete collection")


@router.post("/{collection_id}/users")
async def assign_user_to_collection(
    collection_id: str,
    user_assignment: UserAssignment,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Assign a user to a collection"""
    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Check permissions (super admin or collection admin)
    if current_user.role != "super_admin" and collection.admin_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if user exists
    user = db.query(User).filter(User.user_id == user_assignment.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already assigned
    existing = db.query(CollectionUser).filter(
        CollectionUser.collection_id == collection_id,
        CollectionUser.user_id == user_assignment.user_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User already assigned to collection")
    
    try:
        collection_user = CollectionUser(
            collection_id=collection_id,
            user_id=user_assignment.user_id,
            role=user_assignment.role,
            can_upload=user_assignment.can_upload,
            can_download=user_assignment.can_download,
            can_delete=user_assignment.can_delete,
            assigned_by=current_user.user_id
        )
        
        db.add(collection_user)
        db.commit()
        
        return {"message": "User assigned to collection successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning user to collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign user")


@router.delete("/{collection_id}/users/{user_id}")
async def remove_user_from_collection(
    collection_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a user from a collection"""
    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
    
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Check permissions (super admin or collection admin)
    if current_user.role != "super_admin" and collection.admin_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    collection_user = db.query(CollectionUser).filter(
        CollectionUser.collection_id == collection_id,
        CollectionUser.user_id == user_id
    ).first()
    
    if not collection_user:
        raise HTTPException(status_code=404, detail="User not assigned to collection")
    
    try:
        db.delete(collection_user)
        db.commit()
        
        return {"message": "User removed from collection successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error removing user from collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove user")
