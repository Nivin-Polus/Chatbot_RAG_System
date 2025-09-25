# app/core/permissions.py

from typing import Optional, List, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
import logging

from app.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.website import Website
from app.models.file_metadata import FileMetadata

logger = logging.getLogger(__name__)
security = HTTPBearer()

class PermissionError(HTTPException):
    """Custom permission error"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )

class AuthenticationError(HTTPException):
    """Custom authentication error"""
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    try:
        # Decode JWT token
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        
        if username is None:
            raise AuthenticationError()
        
        # Get user from database
        user = db.query(User).filter(
            User.username == username,
            User.is_active == True
        ).first()
        
        if user is None:
            raise AuthenticationError("User not found or inactive")
        
        return user
        
    except jwt.PyJWTError as e:
        logger.warning(f"JWT validation error: {e}")
        raise AuthenticationError()
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise AuthenticationError()

def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require super admin role"""
    if not current_user.is_super_admin():
        raise PermissionError("Super admin access required")
    return current_user

def require_user_admin_or_super(current_user: User = Depends(get_current_user)) -> User:
    """Require user admin or super admin role"""
    if not (current_user.is_super_admin() or current_user.is_user_admin()):
        raise PermissionError("Admin access required")
    return current_user

def require_admin_or_above(current_user: User = Depends(get_current_user)) -> User:
    """Require admin or above role (alias for require_user_admin_or_super)"""
    return require_user_admin_or_super(current_user)

def require_website_access(website_id: str):
    """Dependency factory for website access control"""
    def _check_website_access(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        # Super admin can access any website
        if current_user.is_super_admin():
            return current_user
        
        # Check if website exists
        website = db.query(Website).filter(Website.website_id == website_id).first()
        if not website:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Website not found"
            )
        
        # Check if user can access this website
        if not current_user.can_access_website(website_id):
            raise PermissionError("Access denied to this website")
        
        return current_user
    
    return _check_website_access

def require_website_management(website_id: str):
    """Dependency factory for website management access"""
    def _check_website_management(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> User:
        # Check if website exists
        website = db.query(Website).filter(Website.website_id == website_id).first()
        if not website:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Website not found"
            )
        
        # Check if user can manage this website
        if not current_user.can_manage_website(website_id):
            raise PermissionError("Website management access denied")
        
        return current_user
    
    return _check_website_management

def require_file_access(file_id: str, permission_type: str = "read"):
    """Dependency factory for file access control"""
    def _check_file_access(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> tuple[User, FileMetadata]:
        # Get file metadata
        file_metadata = db.query(FileMetadata).filter(
            FileMetadata.file_id == file_id
        ).first()
        
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Super admin can access any file
        if current_user.is_super_admin():
            return current_user, file_metadata
        
        # Check website access first
        if not current_user.can_access_website(file_metadata.website_id):
            raise PermissionError("Access denied to this website")
        
        # User admin can access all files in their website
        if current_user.is_user_admin() and current_user.website_id == file_metadata.website_id:
            return current_user, file_metadata
        
        # Regular users need explicit file access
        if current_user.is_regular_user():
            accessible_file_ids = current_user.get_accessible_file_ids(db)
            if file_id not in accessible_file_ids:
                raise PermissionError("Access denied to this file")
        
        return current_user, file_metadata
    
    return _check_file_access

class PermissionChecker:
    """Helper class for checking permissions"""
    
    @staticmethod
    def can_create_website(user: User) -> bool:
        """Check if user can create websites"""
        return user.is_super_admin()
    
    @staticmethod
    def can_delete_website(user: User, website_id: str) -> bool:
        """Check if user can delete a website"""
        return user.is_super_admin()
    
    @staticmethod
    def can_create_user(user: User, target_website_id: Optional[str] = None) -> bool:
        """Check if user can create other users"""
        if user.is_super_admin():
            return True
        
        if user.is_user_admin() and target_website_id == user.website_id:
            return True
        
        return False
    
    @staticmethod
    def can_modify_user(user: User, target_user: User) -> bool:
        """Check if user can modify another user"""
        if user.is_super_admin():
            return True
        
        if user.is_user_admin() and target_user.website_id == user.website_id:
            # User admin can modify users in their website (except other admins)
            return not target_user.is_super_admin()
        
        # Users can modify themselves (limited fields)
        return user.user_id == target_user.user_id
    
    @staticmethod
    def can_upload_file(user: User, website_id: str) -> bool:
        """Check if user can upload files to a website"""
        if user.is_super_admin():
            return True
        
        if user.is_user_admin() and user.website_id == website_id:
            return True
        
        # Regular users can upload if they have access to the website
        return user.can_access_website(website_id)
    
    @staticmethod
    def can_delete_file(user: User, file_metadata: FileMetadata) -> bool:
        """Check if user can delete a file"""
        if user.is_super_admin():
            return True
        
        if user.is_user_admin() and user.website_id == file_metadata.website_id:
            return True
        
        # File uploader can delete their own files
        return user.user_id == file_metadata.uploader_id
    
    @staticmethod
    def can_grant_file_access(user: User, file_metadata: FileMetadata) -> bool:
        """Check if user can grant file access to others"""
        if user.is_super_admin():
            return True
        
        if user.is_user_admin() and user.website_id == file_metadata.website_id:
            return True
        
        # File uploader can grant access to their files
        return user.user_id == file_metadata.uploader_id
    
    @staticmethod
    def can_view_analytics(user: User, website_id: Optional[str] = None) -> bool:
        """Check if user can view analytics"""
        if user.is_super_admin():
            return True
        
        if user.is_user_admin() and (website_id is None or user.website_id == website_id):
            return True
        
        return False
    
    @staticmethod
    def get_accessible_websites(user: User, db: Session) -> List[Website]:
        """Get list of websites user can access"""
        if user.is_super_admin():
            return db.query(Website).filter(Website.is_active == True).all()
        
        if user.website_id:
            website = db.query(Website).filter(
                Website.website_id == user.website_id,
                Website.is_active == True
            ).first()
            return [website] if website else []
        
        return []

# Convenience functions for common permission checks

def check_website_quota(website: Website, db: Session, check_type: str = "users") -> bool:
    """Check if website is within quota limits"""
    if check_type == "users":
        current_count = db.query(User).filter(User.website_id == website.website_id).count()
        return current_count < website.max_users
    
    elif check_type == "files":
        current_count = db.query(FileMetadata).filter(
            FileMetadata.website_id == website.website_id
        ).count()
        return current_count < website.max_files
    
    elif check_type == "storage":
        from sqlalchemy import func
        current_size = db.query(func.sum(FileMetadata.file_size)).filter(
            FileMetadata.website_id == website.website_id
        ).scalar() or 0
        max_size_bytes = website.max_storage_mb * 1024 * 1024
        return current_size < max_size_bytes
    
    return True

def get_user_context(user: User, db: Session) -> Dict[str, Any]:
    """Get user context for API responses"""
    context = {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "website_id": user.website_id,
        "permissions": {
            "is_super_admin": user.is_super_admin(),
            "is_user_admin": user.is_user_admin(),
            "is_regular_user": user.is_regular_user(),
            "can_create_websites": PermissionChecker.can_create_website(user),
            "can_view_global_analytics": user.is_super_admin()
        }
    }
    
    if user.website_id:
        website = db.query(Website).filter(Website.website_id == user.website_id).first()
        if website:
            context["website"] = {
                "website_id": website.website_id,
                "name": website.name,
                "domain": website.domain
            }
    
    return context
