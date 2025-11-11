# app/api/routes_websites.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.permissions import (
    get_current_user, require_super_admin, require_website_management,
    PermissionChecker, check_website_quota, get_user_context
)
from app.models.website import (
    Website, WebsiteCreate, WebsiteUpdate, WebsiteResponse, WebsiteWithStats
)
from app.models.user import User
from app.services.multitenant_vector_store import get_multitenant_vector_store

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[WebsiteResponse])
async def list_websites(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List websites based on user permissions"""
    try:
        if current_user.is_super_admin():
            # Super admin can see all websites
            query = db.query(Website)
            if active_only:
                query = query.filter(Website.is_active == True)
            websites = query.offset(skip).limit(limit).all()
        else:
            # Regular users can only see their own website
            if not current_user.website_id:
                return []
            
            website = db.query(Website).filter(
                Website.website_id == current_user.website_id
            ).first()
            websites = [website] if website and (not active_only or website.is_active) else []
        
        return [WebsiteResponse(**website.to_dict()) for website in websites]
        
    except Exception as e:
        logger.error(f"Failed to list websites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve websites"
        )

@router.get("/{website_id}", response_model=WebsiteWithStats)
async def get_website(
    website_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get website details with statistics"""
    try:
        # Check if website exists
        website = db.query(Website).filter(Website.website_id == website_id).first()
        if not website:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Website not found"
            )
        
        # Check permissions
        if not current_user.can_access_website(website_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this website"
            )
        
        # Get usage statistics
        usage_stats = website.get_usage_stats(db)
        
        # Get vector store statistics
        vector_store = get_multitenant_vector_store()
        vector_stats = vector_store.get_website_stats(website_id)
        
        website_data = website.to_dict()
        website_data["usage_stats"] = {
            **usage_stats,
            "vector_documents": vector_stats.get("document_count", 0)
        }
        
        return WebsiteWithStats(**website_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get website {website_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve website"
        )

@router.post("/", response_model=WebsiteResponse)
async def create_website(
    website_data: WebsiteCreate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Create a new website (super admin only)"""
    try:
        # Check if domain is already taken
        if website_data.domain:
            existing_website = db.query(Website).filter(
                Website.domain == website_data.domain
            ).first()
            if existing_website:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Domain already exists"
                )
        
        # Create website
        website = Website(**website_data.dict())
        db.add(website)
        db.commit()
        db.refresh(website)
        
        logger.info(f"Website created: {website.name} ({website.website_id})")
        
        return WebsiteResponse(**website.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create website: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create website"
        )

@router.put("/{website_id}", response_model=WebsiteResponse)
async def update_website(
    website_id: str,
    website_data: WebsiteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update website (super admin or website admin)"""
    try:
        # Get website
        website = db.query(Website).filter(Website.website_id == website_id).first()
        if not website:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Website not found"
            )
        
        # Check permissions
        if not current_user.can_manage_website(website_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Website management access denied"
            )
        
        # Check domain uniqueness if changing domain
        if website_data.domain and website_data.domain != website.domain:
            existing_website = db.query(Website).filter(
                Website.domain == website_data.domain,
                Website.website_id != website_id
            ).first()
            if existing_website:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Domain already exists"
                )
        
        # Update website
        update_data = website_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(website, field, value)
        
        db.commit()
        db.refresh(website)
        
        logger.info(f"Website updated: {website.name} ({website.website_id})")
        
        return WebsiteResponse(**website.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update website {website_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update website"
        )

@router.delete("/{website_id}")
async def delete_website(
    website_id: str,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Delete website and all associated data (super admin only)"""
    try:
        # Get website
        website = db.query(Website).filter(Website.website_id == website_id).first()
        if not website:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Website not found"
            )
        
        # Delete associated data
        from app.models.user_file_access import UserFileAccess
        from app.models.query_log import QueryLog
        from app.models.file_metadata import FileMetadata
        
        # Delete user file access records
        db.query(UserFileAccess).filter(
            UserFileAccess.file_id.in_(
                db.query(FileMetadata.file_id).filter(
                    FileMetadata.website_id == website_id
                )
            )
        ).delete(synchronize_session=False)
        
        # Delete query logs
        db.query(QueryLog).filter(QueryLog.website_id == website_id).delete()
        
        # Delete file metadata
        db.query(FileMetadata).filter(FileMetadata.website_id == website_id).delete()
        
        # Delete users (except super admins)
        db.query(User).filter(
            User.website_id == website_id,
            User.role != "super_admin"
        ).delete()
        
        # Delete vector store documents
        vector_store = get_multitenant_vector_store()
        vector_store.delete_documents_by_website_id(website_id)
        
        # Delete website
        db.delete(website)
        db.commit()
        
        logger.info(f"Website deleted: {website.name} ({website_id})")
        
        return {"message": "Website deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete website {website_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete website"
        )

@router.get("/{website_id}/users", response_model=List[dict])
async def list_website_users(
    website_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users in a website"""
    try:
        # Check permissions
        if not current_user.can_manage_website(website_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Website management access denied"
            )
        
        # Get users
        users = db.query(User).filter(
            User.website_id == website_id,
            User.is_active == True
        ).offset(skip).limit(limit).all()
        
        return [
            {
                **user.to_dict(),
                "accessible_file_count": len(user.get_accessible_file_ids(db))
            }
            for user in users
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list users for website {website_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )

@router.get("/{website_id}/analytics")
async def get_website_analytics(
    website_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get website analytics and usage statistics"""
    try:
        # Check permissions
        if not PermissionChecker.can_view_analytics(current_user, website_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Analytics access denied"
            )
        
        # Get website
        website = db.query(Website).filter(Website.website_id == website_id).first()
        if not website:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Website not found"
            )
        
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from app.models.query_log import QueryLog
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Query analytics
        query_stats = db.query(
            func.count(QueryLog.query_id).label("total_queries"),
            func.count(func.distinct(QueryLog.user_id)).label("unique_users"),
            func.avg(QueryLog.processing_time_ms).label("avg_processing_time"),
            func.sum(QueryLog.tokens_used).label("total_tokens")
        ).filter(
            QueryLog.website_id == website_id,
            QueryLog.created_at >= start_date
        ).first()
        
        # Get usage stats
        usage_stats = website.get_usage_stats(db)
        
        # Get vector store stats
        vector_store = get_multitenant_vector_store()
        vector_stats = vector_store.get_website_stats(website_id)
        
        return {
            "website_id": website_id,
            "website_name": website.name,
            "period_days": days,
            "query_analytics": {
                "total_queries": query_stats.total_queries or 0,
                "unique_users": query_stats.unique_users or 0,
                "avg_processing_time_ms": float(query_stats.avg_processing_time or 0),
                "total_tokens_used": query_stats.total_tokens or 0
            },
            "usage_stats": usage_stats,
            "vector_stats": vector_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analytics for website {website_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )
