
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import timedelta
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional
from urllib.parse import urlparse
import secrets
import uuid

from app.config import settings
from app.models.user import User
from app.models.collection import Collection, CollectionUser
from app.models.website import Website
from app.core.auth import verify_password, get_password_hash, create_access_token
from app.core.database import get_db

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Issue access token for authenticated users."""
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    from datetime import datetime

    user.last_login = datetime.utcnow()
    db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "user_id": user.user_id,
            "website_id": user.website_id,
        },
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "website_id": user.website_id,
        "user_id": user.user_id,
    }


# Dependency to get current user from JWT
async def get_current_user(token: str = Depends(oauth2_scheme)):
    import jwt
    from jwt import InvalidTokenError

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        user_id: str = payload.get("user_id")
        website_id: str = payload.get("website_id")
        collection_id: Optional[str] = payload.get("collection_id")
        auth_type: str = payload.get("auth_type", "user")
        session_id: Optional[str] = payload.get("session_id")

        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        return {
            "username": username,
            "role": role,
            "user_id": user_id,
            "website_id": website_id,
            "collection_id": collection_id,
            "auth_type": auth_type,
            "session_id": session_id,
        }
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change the authenticated user's password."""

    # Get current user from database
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Validate new password
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long")
    
    # Update password in database
    user.password_hash = get_password_hash(request.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}

# Verify token endpoint
@router.get("/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """Verify if the current JWT token is valid"""
    return {
        "valid": True,
        "user": current_user["username"],
        "role": current_user["role"]
    }


class PublicTokenRequest(BaseModel):
    website_url: str
    session_id: Optional[str] = None


class PublicTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    collection_id: str
    collection_name: str
    session_id: str
    expires_in: int


def normalize_domain(url: str) -> Optional[str]:
    if not url:
        return None

    if "://" not in url:
        url = f"https://{url}"

    parsed = urlparse(url)
    domain = (parsed.netloc or parsed.path).lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain or None


def find_collection_by_domain(domain: str, db: Session) -> Optional[Collection]:
    if not domain:
        return None

    collection = (
        db.query(Collection)
        .filter(Collection.is_active == True)
        .filter(Collection.website_url.isnot(None))
        .filter(func.lower(Collection.website_url).like(f"%{domain}%"))
        .first()
    )

    if collection:
        return collection

    collection = (
        db.query(Collection)
        .join(Website, Website.website_id == Collection.website_id, isouter=True)
        .filter(Collection.is_active == True)
        .filter(Website.domain.isnot(None))
        .filter(func.lower(Website.domain) == domain)
        .first()
    )

    return collection


def ensure_public_user(collection: Collection, db: Session) -> User:
    public_username = f"public_{collection.collection_id}"

    public_user = db.query(User).filter(User.username == public_username).first()

    if not public_user:
        random_password = secrets.token_urlsafe(32)
        public_user = User(
            username=public_username,
            email=None,
            password_hash=get_password_hash(random_password),
            full_name=f"Public User for {collection.name}",
            role="user",
            is_active=True,
            website_id=collection.website_id,
        )
        db.add(public_user)
        db.flush()

    membership = (
        db.query(CollectionUser)
        .filter(
            CollectionUser.collection_id == collection.collection_id,
            CollectionUser.user_id == public_user.user_id,
        )
        .first()
    )

    if not membership:
        membership = CollectionUser(
            collection_id=collection.collection_id,
            user_id=public_user.user_id,
            role="user",
            can_upload=False,
            can_download=True,
            can_delete=False,
            assigned_by=collection.admin_user_id or public_user.user_id,
        )
        db.add(membership)

    return public_user


@router.post("/public/token", response_model=PublicTokenResponse)
async def create_public_token(request: PublicTokenRequest, db: Session = Depends(get_db)):
    domain = normalize_domain(request.website_url)

    if not domain:
        raise HTTPException(status_code=400, detail="Invalid website URL provided")

    collection = find_collection_by_domain(domain, db)

    if not collection:
        raise HTTPException(status_code=404, detail="No collection is mapped to this website")

    if not collection.is_active:
        raise HTTPException(status_code=403, detail="Collection is inactive")

    public_user = ensure_public_user(collection, db)

    session_id = request.session_id or str(uuid.uuid4())

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_payload = {
        "sub": public_user.username,
        "role": public_user.role,
        "user_id": public_user.user_id,
        "website_id": public_user.website_id,
        "collection_id": collection.collection_id,
        "auth_type": "public",
        "session_id": session_id,
    }

    access_token = create_access_token(data=token_payload, expires_delta=access_token_expires)

    db.commit()

    return PublicTokenResponse(
        access_token=access_token,
        collection_id=collection.collection_id,
        collection_name=collection.name,
        session_id=session_id,
        expires_in=int(access_token_expires.total_seconds()),
    )
