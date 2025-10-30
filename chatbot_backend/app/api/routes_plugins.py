from __future__ import annotations

import logging
import secrets
import re
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.core.auth import create_plugin_user_token, get_password_hash
from app.models.collection import Collection, CollectionUser
from app.models.plugin_integration import PluginIntegration
from app.models.user import User

router = APIRouter(prefix="/plugins", tags=["Plugins"])
logger = logging.getLogger(__name__)


class PluginIntegrationBase(BaseModel):
    collection_id: str
    website_url: str
    display_name: Optional[str] = None


class PluginIntegrationCreate(PluginIntegrationBase):
    pass


class PluginIntegrationUpdate(BaseModel):
    website_url: Optional[str] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


class PluginIntegrationResponse(BaseModel):
    id: int
    collection_id: str
    collection_name: str
    website_url: str
    normalized_url: str
    display_name: Optional[str]
    is_active: bool
    created_at: Optional[str]
    created_by: Optional[str]
    plugin_username: Optional[str] = None
    plugin_password: Optional[str] = None
    plugin_token: Optional[str] = None

    class Config:
        from_attributes = True


_USERNAME_MAX_LENGTH = 100
_USERNAME_SUFFIX = "_plugin"
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


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


def _user_accessible_collection_ids(current_user: User, db: Session) -> List[str]:
    if current_user.is_super_admin():
        return [row[0] for row in db.query(Collection.collection_id).all()]

    if current_user.is_user_admin():
        return [
            row[0]
            for row in db.query(Collection.collection_id)
            .filter(Collection.admin_user_id == current_user.user_id)
            .all()
        ]

    # Regular users only see collections they are assigned to
    from app.models.collection import CollectionUser

    return [
        row[0]
        for row in db.query(CollectionUser.collection_id)
        .filter(CollectionUser.user_id == current_user.user_id)
        .all()
    ]


def _to_response(plugin: PluginIntegration) -> PluginIntegrationResponse:
    return PluginIntegrationResponse(
        id=plugin.id,
        collection_id=plugin.collection_id,
        collection_name=plugin.collection.name if plugin.collection else "",
        website_url=plugin.website_url,
        normalized_url=plugin.normalized_url,
        display_name=plugin.display_name,
        is_active=plugin.is_active,
        created_at=plugin.created_at.isoformat() if plugin.created_at else None,
        created_by=plugin.created_by,
        plugin_username=None,
        plugin_password=None,
        plugin_token=None,
    )


def _slugify(value: str) -> str:
    return _SLUG_PATTERN.sub("", value.lower())


def _ensure_unique_username(db: Session, base: str) -> str:
    base = base[:_USERNAME_MAX_LENGTH] or "plugin"
    candidate = base
    counter = 1
    while db.query(User).filter(User.username == candidate).first():
        suffix = f"_{counter}"
        candidate = f"{base[:_USERNAME_MAX_LENGTH - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def _generate_plugin_username(db: Session, normalized_url: str, collection: Collection) -> str:
    candidates = []
    if normalized_url:
        candidates.append(normalized_url.split("/")[0])
    if collection.name:
        candidates.append(collection.name)
    candidates.append(collection.collection_id)

    for candidate in candidates:
        root = _slugify(candidate)
        if not root:
            continue
        username = _ensure_unique_username(db, f"{root}{_USERNAME_SUFFIX}")
        if username:
            return username

    return _ensure_unique_username(db, f"plugin_{secrets.token_hex(3)}")


def _ensure_plugin_user_for_collection(
    db: Session,
    *,
    collection: Collection,
    plugin: PluginIntegration,
    creator_user_id: Optional[str],
) -> tuple[User, Optional[str], Optional[str]]:
    plugin_user = (
        db.query(User)
        .join(CollectionUser, CollectionUser.user_id == User.user_id)
        .filter(
            CollectionUser.collection_id == collection.collection_id,
            User.role == "plugin_user",
        )
        .first()
    )

    generated_password: Optional[str] = None
    plugin_token_value: Optional[str] = None

    if not plugin_user:
        username = _generate_plugin_username(db, plugin.normalized_url, collection)
        generated_password = secrets.token_urlsafe(12)
        plugin_user = User(
            username=username,
            email=None,
            password_hash=get_password_hash(generated_password),
            full_name=f"{collection.name} Plugin User" if collection.name else "Plugin User",
            role="plugin_user",
            website_id=collection.website_id,
            is_active=plugin.is_active,
        )
        db.add(plugin_user)
        db.flush()

        membership = CollectionUser(
            collection_id=collection.collection_id,
            user_id=plugin_user.user_id,
            role="plugin",
            can_upload=False,
            can_download=True,
            can_delete=False,
            assigned_by=creator_user_id or collection.admin_user_id,
        )
        db.add(membership)

        if plugin.is_active:
            plugin_token_value = create_plugin_user_token(
                user_id=plugin_user.user_id,
                username=plugin_user.username,
                password=generated_password,
                collection_id=collection.collection_id,
            )
            plugin_user.plugin_token = plugin_token_value
        else:
            plugin_user.plugin_token = None
    else:
        if plugin_user.is_active != plugin.is_active:
            plugin_user.is_active = plugin.is_active

        membership = (
            db.query(CollectionUser)
            .filter(
                CollectionUser.collection_id == collection.collection_id,
                CollectionUser.user_id == plugin_user.user_id,
            )
            .first()
        )
        if not membership:
            membership = CollectionUser(
                collection_id=collection.collection_id,
                user_id=plugin_user.user_id,
                role="plugin",
                can_upload=False,
                can_download=True,
                can_delete=False,
                assigned_by=creator_user_id or collection.admin_user_id,
            )
            db.add(membership)

        if plugin.is_active:
            # For existing plugin users, if we're doing a lookup (creator_user_id is None)
            # or if there's no existing token, generate a fresh token
            if creator_user_id is None or not plugin_user.plugin_token:
                # Generate a fresh token for active plugins
                plugin_token_value = create_plugin_user_token(
                    user_id=plugin_user.user_id,
                    username=plugin_user.username,
                    password="",  # Password not stored in plain text, but token can be regenerated
                    collection_id=collection.collection_id,
                )
                plugin_user.plugin_token = plugin_token_value
            else:
                plugin_token_value = plugin_user.plugin_token
        else:
            plugin_user.plugin_token = None
            plugin_token_value = None

    return plugin_user, generated_password, plugin_token_value


@router.get("/", response_model=List[PluginIntegrationResponse])
async def list_plugins(
    collection_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accessible_ids = _user_accessible_collection_ids(current_user, db)

    if not accessible_ids:
        return []

    query = db.query(PluginIntegration).join(Collection)

    if collection_id:
        if collection_id not in accessible_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        query = query.filter(PluginIntegration.collection_id == collection_id)
    else:
        query = query.filter(PluginIntegration.collection_id.in_(accessible_ids))

    plugins = query.order_by(PluginIntegration.created_at.desc()).all()
    responses: List[PluginIntegrationResponse] = []
    for plugin in plugins:
        response = _to_response(plugin)
        response.collection_name = plugin.collection.name if plugin.collection else ""
        plugin_user = (
            db.query(User)
            .join(CollectionUser, CollectionUser.user_id == User.user_id)
            .filter(
                CollectionUser.collection_id == plugin.collection_id,
                User.role == "plugin_user",
            )
            .first()
        )
        if plugin_user:
            response.plugin_username = plugin_user.username
            if plugin_user.is_active and plugin.is_active:
                response.plugin_token = plugin_user.plugin_token
        responses.append(response)
    return responses


@router.post("/", response_model=PluginIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_plugin(
    payload: PluginIntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    collection = db.query(Collection).filter(Collection.collection_id == payload.collection_id).first()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    if not current_user.is_super_admin():
        if not current_user.is_user_admin() or collection.admin_user_id != current_user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    normalized = _normalize_url(payload.website_url)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")

    existing = (
        db.query(PluginIntegration)
        .filter(PluginIntegration.normalized_url == normalized)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This URL is already linked to another knowledge base")

    plugin = PluginIntegration(
        collection_id=payload.collection_id,
        website_url=payload.website_url.strip(),
        normalized_url=normalized,
        display_name=payload.display_name.strip() if payload.display_name else None,
        is_active=True,
        created_by=current_user.user_id,
    )

    db.add(plugin)
    db.commit()
    db.refresh(plugin)

    plugin_user, generated_password, plugin_token_value = _ensure_plugin_user_for_collection(
        db,
        collection=collection,
        plugin=plugin,
        creator_user_id=current_user.user_id,
    )
    db.commit()
    db.refresh(plugin_user)

    logger.info("Plugin integration created: %s -> %s", plugin.collection_id, plugin.normalized_url)
    response = _to_response(plugin)
    response.collection_name = collection.name
    response.plugin_username = plugin_user.username
    response.plugin_password = generated_password
    response.plugin_token = plugin_token_value
    return response


class PluginLookupRequest(BaseModel):
    website_url: str


class PluginLookupResponse(BaseModel):
    is_active: bool
    collection_id: str
    collection_name: str
    plugin_username: str
    plugin_token: Optional[str]


@router.post("/lookup", response_model=PluginLookupResponse)
async def lookup_plugin_credentials(
    payload: PluginLookupRequest,
    db: Session = Depends(get_db),
):
    normalized = _normalize_url(payload.website_url)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")

    # Find plugin by doing a prefix match instead of exact match
    # This allows subpaths like /login or /hero to match the base domain
    plugin = (
        db.query(PluginIntegration)
        .join(Collection, PluginIntegration.collection_id == Collection.collection_id)
        .filter(PluginIntegration.normalized_url == normalized)
        .first()
    )
    
    # If exact match fails, try prefix matching
    # This allows subpaths like /login or /hero to match a base domain registration
    if not plugin:
        # Parse the normalized URL to get domain and path
        parsed_request = urlparse(f"https://{normalized}" if "://" not in normalized else normalized)
        request_domain = parsed_request.netloc.lower()
        request_path = parsed_request.path.rstrip('/')
        
        # Try to match plugins by checking if the request URL is a subpath of a registered plugin URL
        # or if the plugin URL is a subpath of the request URL
        plugins = (
            db.query(PluginIntegration)
            .join(Collection, PluginIntegration.collection_id == Collection.collection_id)
            .all()
        )
        
        for p in plugins:
            # Parse the plugin's normalized URL
            parsed_plugin = urlparse(f"https://{p.normalized_url}" if "://" not in p.normalized_url else p.normalized_url)
            plugin_domain = parsed_plugin.netloc.lower()
            plugin_path = parsed_plugin.path.rstrip('/')
            
            # Check if domains match
            if request_domain == plugin_domain:
                # Same domain, check paths
                # If plugin is registered with base domain, it should match any subpath
                # If plugin is registered with a specific path, the request path should start with it
                if not plugin_path or request_path.startswith(plugin_path):
                    plugin = p
                    break
    
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin not found for the provided URL")

    collection = plugin.collection
    active = plugin.is_active and (collection.is_active if collection and hasattr(collection, "is_active") else True)

    plugin_user, _, plugin_token_value = _ensure_plugin_user_for_collection(
        db,
        collection=collection,
        plugin=plugin,
        creator_user_id=None,
    )

    if not plugin_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin user not configured for collection")

    if not plugin_user.is_active:
        active = False
        plugin_token_value = None
    else:
        if not plugin_token_value and active:
            plugin_token_value = plugin_user.plugin_token

    return PluginLookupResponse(
        is_active=active,
        collection_id=plugin.collection_id,
        collection_name=collection.name if collection else "",
        plugin_username=plugin_user.username,
        plugin_token=plugin_token_value,
    )


@router.put("/{plugin_id}", response_model=PluginIntegrationResponse)
async def update_plugin(
    plugin_id: int,
    payload: PluginIntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plugin = db.query(PluginIntegration).filter(PluginIntegration.id == plugin_id).first()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin integration not found")

    collection = plugin.collection
    if not current_user.is_super_admin():
        if not current_user.is_user_admin() or not collection or collection.admin_user_id != current_user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if payload.website_url is not None:
        normalized = _normalize_url(payload.website_url)
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")

        duplicate = (
            db.query(PluginIntegration)
            .filter(
                PluginIntegration.normalized_url == normalized,
                PluginIntegration.id != plugin.id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This URL is already linked to another knowledge base")

        plugin.website_url = payload.website_url.strip()
        plugin.normalized_url = normalized

    if payload.display_name is not None:
        plugin.display_name = payload.display_name.strip() or None

    if payload.is_active is not None:
        plugin.is_active = payload.is_active

    plugin_user, generated_password, plugin_token_value = _ensure_plugin_user_for_collection(
        db,
        collection=collection,
        plugin=plugin,
        creator_user_id=current_user.user_id,
    )
    
    db.commit()
    db.refresh(plugin)

    logger.info("Plugin integration updated: %s (active=%s)", plugin.id, plugin.is_active)
    response = _to_response(plugin)
    response.collection_name = collection.name if collection else ""
    response.plugin_username = plugin_user.username if plugin_user else None
    response.plugin_password = generated_password
    response.plugin_token = plugin_token_value
    return response


@router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin(
    plugin_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plugin = db.query(PluginIntegration).filter(PluginIntegration.id == plugin_id).first()
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin integration not found")

    collection = plugin.collection
    if not current_user.is_super_admin():
        if not current_user.is_user_admin() or not collection or collection.admin_user_id != current_user.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    db.delete(plugin)
    db.commit()

    logger.info("Plugin integration deleted: %s", plugin.id)
