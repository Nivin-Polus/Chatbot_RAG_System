
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.core.permissions import (
    get_current_user, require_super_admin, PermissionChecker, 
    check_website_quota, get_user_context
)
from app.core.auth import create_user, get_password_hash
from app.models.user import (
    User, UserCreate, UserUpdate, UserResponse, UserWithPermissions
)
from app.models.website import Website
from app.models.collection import Collection, CollectionUser

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_managed_collection(
    db: Session,
    current_user: User,
    collection_id: str
) -> Collection:
    """Return collection if the current user can administer it."""

    collection = db.query(Collection).filter(Collection.collection_id == collection_id).first()
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )

    if current_user.is_super_admin():
        return collection

    if collection.admin_user_id == current_user.user_id:
        return collection

    membership = db.query(CollectionUser).filter(
        CollectionUser.collection_id == collection_id,
        CollectionUser.user_id == current_user.user_id,
        CollectionUser.role == "admin"
    ).first()

    if membership:
        return collection

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not allowed to manage this collection"
    )

@router.get("/me", response_model=UserWithPermissions)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user information with permissions"""
    try:
        # Get accessible file IDs
        accessible_file_ids = current_user.get_accessible_file_ids(db)
        
        # Build response with permissions
        user_data = current_user.to_dict()
        user_data.update({
            "accessible_file_ids": accessible_file_ids,
            "can_upload_files": PermissionChecker.can_upload_file(
                current_user, current_user.website_id or ""
            ),
            "can_manage_users": current_user.is_super_admin() or current_user.is_user_admin(),
            "can_manage_website": current_user.can_manage_website(current_user.website_id or "")
        })
        
        return UserWithPermissions(**user_data)
        
    except Exception as e:
        logger.error(f"Failed to get current user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information"
        )

@router.get("/", response_model=List[UserResponse])
async def list_users(
    website_id: Optional[str] = Query(None),
    collection_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    role: Optional[str] = Query(None),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users based on permissions"""
    try:
        query = db.query(User)
        
        if current_user.is_super_admin():
            # Super admin can see all users
            if website_id:
                query = query.filter(User.website_id == website_id)
        elif current_user.is_user_admin():
            # User admin can only see users in their website
            query = query.filter(User.website_id == current_user.website_id)
        else:
            # Regular users can only see themselves
            query = query.filter(User.user_id == current_user.user_id)
        
        # Apply filters
        if role:
            query = query.filter(User.role == role)
        if active_only:
            query = query.filter(User.is_active == True)
        if collection_id:
            query = query.join(CollectionUser, CollectionUser.user_id == User.user_id)
            query = query.filter(CollectionUser.collection_id == collection_id)
        
        users = query.offset(skip).limit(limit).all()
        
        return [UserResponse(**user.to_dict()) for user in users]
        
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )

@router.get("/{user_id}", response_model=UserWithPermissions)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user details with permissions"""
    try:
        # Get target user
        target_user = db.query(User).filter(User.user_id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check permissions
        if not PermissionChecker.can_modify_user(current_user, target_user):
            # Allow viewing basic info if in same website
            if (current_user.website_id != target_user.website_id and 
                not current_user.is_super_admin()):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        
        # Get accessible file IDs
        accessible_file_ids = target_user.get_accessible_file_ids(db)
        
        # Build response
        user_data = target_user.to_dict()
        user_data.update({
            "accessible_file_ids": accessible_file_ids,
            "can_upload_files": PermissionChecker.can_upload_file(
                target_user, target_user.website_id or ""
            ),
            "can_manage_users": target_user.is_super_admin() or target_user.is_user_admin(),
            "can_manage_website": target_user.can_manage_website(target_user.website_id or "")
        })
        
        return UserWithPermissions(**user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )

@router.post("/", response_model=UserResponse)
async def create_new_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new user"""
    try:
        # Validate and resolve target collection
        collection = None
        if user_data.role != "super_admin":
            if not user_data.collection_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="collection_id is required for non super-admin users"
                )

        if user_data.collection_id:
            collection = _get_managed_collection(db, current_user, user_data.collection_id)

        # Determine target website for permission checks
        target_website_id = user_data.website_id
        if collection:
            target_website_id = collection.website_id or target_website_id or current_user.website_id

        # Validate permissions
        if not PermissionChecker.can_create_user(current_user, target_website_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User creation access denied"
            )
        
        # Check if website exists (only if website_id is provided)
        if user_data.website_id:
            website = db.query(Website).filter(
                Website.website_id == user_data.website_id
            ).first()
            if not website:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Website not found"
                )
            
            # Check website quota
            if not check_website_quota(website, db, "users"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Website user quota exceeded"
                )
        
        # Check if username already exists globally (since website is now optional)
        existing_user = db.query(User).filter(
            User.username == user_data.username
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Validate role permissions
        if user_data.role == "super_admin" and not current_user.is_super_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can create super admin users"
            )
        
        # Determine website from collection if needed
        effective_website_id = target_website_id

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            website_id=effective_website_id,
            role=user_data.role,
            is_active=True
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Ensure collection assignment exists
        if user_data.collection_id:
            assignment = db.query(CollectionUser).filter(
                CollectionUser.collection_id == user_data.collection_id,
                CollectionUser.user_id == new_user.user_id
            ).first()
            if not assignment:
                assignment = CollectionUser(
                    collection_id=user_data.collection_id,
                    user_id=new_user.user_id,
                    role="admin" if new_user.role == "user_admin" else "user",
                    can_upload=True,
                    can_download=True,
                    can_delete=new_user.role == "user_admin",
                    assigned_by=current_user.user_id
                )
                db.add(assignment)
                db.commit()

        logger.info(f"User created: {new_user.username} ({new_user.user_id})")

        return UserResponse(**new_user.to_dict())
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

class AdminResetPasswordRequest(BaseModel):
    user_id: str
    new_password: str

@router.post("/reset-password")
async def admin_reset_password(
    request: AdminResetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Super admin can reset any user's password"""
    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if current_user.is_super_admin():
        pass
    else:
        if not PermissionChecker.can_modify_user(current_user, user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to reset this password"
            )
        if user.is_super_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot reset password for super admin users"
            )

    user.password_hash = get_password_hash(request.new_password)
    db.commit()

    logger.info(f"Password reset by super admin for user {user.username} ({user.user_id})")

    return {"message": "Password reset successfully"}

@router.get("/{user_id}/accessible-files")
async def get_user_accessible_files(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of files accessible to a user"""
    try:
        # Get target user
        target_user = db.query(User).filter(User.user_id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check permissions
        if not PermissionChecker.can_modify_user(current_user, target_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get accessible file IDs
        accessible_file_ids = target_user.get_accessible_file_ids(db)
        
        # Get file details
        from app.models.file_metadata import FileMetadata
        files = db.query(FileMetadata).filter(
            FileMetadata.file_id.in_(accessible_file_ids)
        ).all() if accessible_file_ids else []
        
        return {
            "user_id": user_id,
            "username": target_user.username,
            "accessible_file_count": len(accessible_file_ids),
            "files": [
                {
                    "file_id": file.file_id,
                    "file_name": file.file_name,
                    "file_type": file.file_type,
                    "file_size": file.file_size,
                    "upload_timestamp": file.upload_timestamp.isoformat() if file.upload_timestamp else None
                }
                for file in files
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get accessible files for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve accessible files"
        )
