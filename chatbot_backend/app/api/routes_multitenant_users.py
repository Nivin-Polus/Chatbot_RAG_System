
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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
from app.models.file_metadata import FileMetadata

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
    active_only: bool = Query(False),  # Changed to False to show disabled users by default
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users based on permissions (includes inactive users by default)"""
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

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete a user and clean up all related records.
    Deletes: uploaded files, memberships, file access, chat sessions, query logs.
    Prevents deletion if user is admin of any collections.
    """
    # Only super admins can delete anyone; user admins can delete users within their website
    target_user = db.query(User).filter(User.user_id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent deletion of superadmin accounts
    if target_user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete super admin accounts. Super admins are protected system accounts."
        )
    
    # Check permissions: super admin can delete anyone (except superadmins), user admin can delete in their website
    if not current_user.is_super_admin():
        # Non-super admins need permission check
        if not PermissionChecker.can_modify_user(current_user, target_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    try:
        from app.models.file_metadata import FileMetadata
        from app.models.collection import Collection
        from app.models.chat_tracking import ChatSession, ChatQuery
        from app.models.query_log import QueryLog
        
        # Check if user is admin of any collections that still exist
        admin_collections = db.query(Collection).filter(Collection.admin_user_id == user_id).all()
        if admin_collections:
            collection_names = [c.name for c in admin_collections]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete user who is admin of collection(s): {', '.join(collection_names)}. Delete the collection(s) first."
            )
        
        # Delete files uploaded by this user (with synchronize_session=False)
        db.query(FileMetadata).filter(FileMetadata.uploader_id == user_id).delete(synchronize_session=False)
        
        # Remove collection memberships
        db.query(CollectionUser).filter(CollectionUser.user_id == user_id).delete(synchronize_session=False)

        # Revoke file access entries if model exists
        try:
            from app.models.user_file_access import UserFileAccess
            db.query(UserFileAccess).filter(UserFileAccess.user_id == user_id).delete(synchronize_session=False)
        except Exception:
            logger.debug("UserFileAccess model not available or cleanup failed", exc_info=True)

        # Remove chat queries and sessions for this user
        session_ids = [session.session_id for session in db.query(ChatSession.session_id).filter(ChatSession.user_id == user_id).all()]
        if session_ids:
            db.query(ChatQuery).filter(ChatQuery.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(ChatSession).filter(ChatSession.user_id == user_id).delete(synchronize_session=False)

        # Remove query logs associated with this user
        db.query(QueryLog).filter(QueryLog.user_id == user_id).delete(synchronize_session=False)

        # Hard delete: actually remove user from database
        db.delete(target_user)
        db.commit()
        
        logger.info(f"User {target_user.username} ({user_id}) permanently deleted")
    except Exception as exc:
        db.rollback()
        logger.error("Failed to delete user %s: %s", user_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete user")

    return None


@router.post("/", response_model=UserResponse)
async def create_new_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new user"""
    try:
        # Normalize collection identifiers
        incoming_collection_ids = set(filter(None, (user_data.collection_ids or [])))
        if user_data.collection_id:
            incoming_collection_ids.add(user_data.collection_id)

        if user_data.role != "super_admin" and not incoming_collection_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one collection must be provided for non super-admin users"
            )

        # Validate collections and gather metadata
        managed_collections: List[Collection] = []
        for collection_id in incoming_collection_ids:
            collection = _get_managed_collection(db, current_user, collection_id)
            managed_collections.append(collection)

        # Ensure all selected collections belong to the same website (when defined)
        collection_website_ids = {
            collection.website_id for collection in managed_collections if collection.website_id
        }
        if user_data.website_id:
            collection_website_ids.add(user_data.website_id)
        if len(collection_website_ids) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected collections span multiple websites. Choose collections from a single website or specify a matching website_id."
            )

        # Determine target website for permission checks
        target_website_id = user_data.website_id
        if managed_collections:
            target_website_id = managed_collections[0].website_id or target_website_id or current_user.website_id

        # Validate permissions with detailed error messages
        if not PermissionChecker.can_create_user(current_user, target_website_id):
            if current_user.is_user_admin():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User admin can only create users in their website. Your website: {current_user.website_id}, Target collection website: {target_website_id}. Ensure the collection belongs to your website."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User creation access denied. Only super admins and user admins can create users."
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

        existing_email_user = None
        if user_data.email:
            existing_email_user = db.query(User).filter(
                User.email == user_data.email
            ).first()

        # Validate role permissions
        if user_data.role == "super_admin" and not current_user.is_super_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can create super admin users"
            )

        # Determine website from collections if needed
        effective_website_id = target_website_id
        if not effective_website_id and managed_collections:
            effective_website_id = managed_collections[0].website_id

        reactivated = False
        target_user: Optional[User] = None

        if existing_user:
            if existing_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
            target_user = existing_user

        if existing_email_user and (not target_user or existing_email_user.user_id != target_user.user_id):
            if existing_email_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            target_user = existing_email_user

        if target_user:
            if target_user.is_super_admin() and not current_user.is_super_admin():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only super admins can reactivate super admin accounts"
                )

            # Reactivate and update existing user
            target_user.username = user_data.username
            target_user.email = user_data.email
            target_user.full_name = user_data.full_name
            target_user.password_hash = get_password_hash(user_data.password)
            target_user.role = user_data.role
            target_user.is_active = True
            target_user.website_id = effective_website_id

            # Clear memberships; will be re-added below
            db.query(CollectionUser).filter(
                CollectionUser.user_id == target_user.user_id
            ).delete(synchronize_session=False)

            new_user = target_user
            reactivated = True
        else:
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
            db.flush()

        # Ensure collection assignments exist
        membership_role = "admin" if new_user.role == "user_admin" else "user"
        persisted_collection_ids: set[str] = set()

        for collection in managed_collections:
            assignment = db.query(CollectionUser).filter(
                CollectionUser.collection_id == collection.collection_id,
                CollectionUser.user_id == new_user.user_id
            ).first()
            if not assignment:
                assignment = CollectionUser(
                    collection_id=collection.collection_id,
                    user_id=new_user.user_id,
                    role=membership_role,
                    can_upload=True,
                    can_download=True,
                    can_delete=new_user.role == "user_admin",
                    assigned_by=current_user.user_id
                )
                db.add(assignment)
            else:
                assignment.role = membership_role
                assignment.can_delete = new_user.role == "user_admin"
            persisted_collection_ids.add(collection.collection_id)

        if incoming_collection_ids:
            if persisted_collection_ids:
                db.query(CollectionUser).filter(
                    CollectionUser.user_id == new_user.user_id,
                    CollectionUser.collection_id.notin_(persisted_collection_ids)
                ).delete(synchronize_session=False)
            else:
                db.query(CollectionUser).filter(
                    CollectionUser.user_id == new_user.user_id
                ).delete(synchronize_session=False)
        else:
            db.query(CollectionUser).filter(
                CollectionUser.user_id == new_user.user_id
            ).delete(synchronize_session=False)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            error_msg = str(getattr(exc.orig, "args", [None, str(exc)])[-1]) if getattr(exc.orig, "args", None) else str(exc)

            if "users.username" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )

            if "users.email" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate user detected"
            )
        db.refresh(new_user)

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


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile/role information."""
    # Fetch user
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Permission checks
    if not PermissionChecker.can_modify_user(current_user, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if user.is_super_admin() and not current_user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can modify super admin accounts"
        )

    if user_update.role and user_update.role == "super_admin" and not current_user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can promote to super admin"
        )

    try:
        has_changes = False
        collections_provided = (
            user_update.collection_ids is not None or user_update.collection_id is not None
        )

        incoming_collection_ids = set()
        if user_update.collection_ids is not None:
            has_changes = True
            incoming_collection_ids.update(filter(None, user_update.collection_ids))
        if user_update.collection_id is not None:
            has_changes = True
            if user_update.collection_id:
                incoming_collection_ids.add(user_update.collection_id)

        if user_update.full_name is not None:
            user.full_name = user_update.full_name
            has_changes = True

        if user_update.email is not None:
            existing_email = db.query(User).filter(
                User.email == user_update.email,
                User.user_id != user.user_id
            ).first() if user_update.email else None
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email is already in use"
                )
            user.email = user_update.email
            has_changes = True

        if user_update.is_active is not None:
            if user.user_id == current_user.user_id and not user_update.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You cannot deactivate your own account"
                )
            user.is_active = user_update.is_active
            has_changes = True

        if user_update.role is not None:
            # Only allow role change when requesting user has sufficient privilege
            if not current_user.is_super_admin():
                if user_update.role not in {"user", "user_admin"}:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions to set this role"
                    )
                if user.is_super_admin():
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot modify super admin role"
                    )
            user.role = user_update.role
            has_changes = True

        if collections_provided:
            managed_collections: List[Collection] = []
            for collection_id in incoming_collection_ids:
                collection = _get_managed_collection(db, current_user, collection_id)
                managed_collections.append(collection)

            collection_website_ids = {
                collection.website_id for collection in managed_collections if collection.website_id
            }

            if len(collection_website_ids) > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected collections span multiple websites. Choose collections from a single website."
                )

            membership_role = "admin" if user.role == "user_admin" else "user"
            persisted_collection_ids: set[str] = set()

            for collection in managed_collections:
                membership = db.query(CollectionUser).filter(
                    CollectionUser.collection_id == collection.collection_id,
                    CollectionUser.user_id == user.user_id
                ).first()
                if not membership:
                    membership = CollectionUser(
                        collection_id=collection.collection_id,
                        user_id=user.user_id,
                        role=membership_role,
                        can_upload=True,
                        can_download=True,
                        can_delete=user.role == "user_admin",
                        assigned_by=current_user.user_id
                    )
                    db.add(membership)
                else:
                    membership.role = membership_role
                    membership.can_delete = user.role == "user_admin"
                persisted_collection_ids.add(collection.collection_id)

            if incoming_collection_ids:
                if persisted_collection_ids:
                    db.query(CollectionUser).filter(
                        CollectionUser.user_id == user.user_id,
                        CollectionUser.collection_id.notin_(persisted_collection_ids)
                    ).delete(synchronize_session=False)
                else:
                    db.query(CollectionUser).filter(
                        CollectionUser.user_id == user.user_id
                    ).delete(synchronize_session=False)
            else:
                db.query(CollectionUser).filter(
                    CollectionUser.user_id == user.user_id
                ).delete(synchronize_session=False)

            if managed_collections and not user.is_super_admin():
                primary_collection = managed_collections[0]
                if primary_collection.website_id:
                    user.website_id = primary_collection.website_id
            elif not incoming_collection_ids and not user.is_super_admin():
                user.website_id = None

        if not has_changes:
            return UserResponse(**user.to_dict())

        db.commit()
        db.refresh(user)
        return UserResponse(**user.to_dict())

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Failed to update user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
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

@router.get("/me/accessible-files")
async def get_my_accessible_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of files accessible to the current user"""
    try:
        from app.models.user_file_access import UserFileAccess
        
        if current_user.is_super_admin():
            # Super admin can access all files
            files = db.query(FileMetadata).all()
        elif current_user.is_user_admin():
            # User admin can access files in their website
            files = db.query(FileMetadata).filter(
                FileMetadata.website_id == current_user.website_id
            ).all()
        else:
            # Regular user can only access explicitly granted files
            file_access_records = db.query(UserFileAccess).filter(
                UserFileAccess.user_id == current_user.user_id,
                UserFileAccess.can_read == True
            ).all()
            
            file_ids = [record.file_id for record in file_access_records]
            if not file_ids:
                files = []
            else:
                files = db.query(FileMetadata).filter(
                    FileMetadata.file_id.in_(file_ids)
                ).all()
        
        return [
            {
                "file_id": file.file_id,
                "filename": file.filename,
                "file_type": file.file_type,
                "file_size": file.file_size,
                "upload_date": file.upload_date.isoformat() if file.upload_date else None,
                "uploader_username": file.uploader_username,
                "description": file.description,
                "tags": file.tags or []
            }
            for file in files
        ]
        
    except Exception as e:
        logger.error(f"Error getting accessible files for user {current_user.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve accessible files"
        )

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
