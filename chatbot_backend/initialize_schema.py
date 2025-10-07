#!/usr/bin/env python3
"""
Initializes the chatbot multi-tenant schema and inserts default data.

Run this script the first time you point the application at a fresh database
schema. It will:
  1. Create the database (MySQL) if it does not exist yet.
  2. Create all ORM tables using the current SQLAlchemy metadata.
  3. Ensure default website, users, collection, and prompt records exist.

Usage:
    python initialize_schema.py

Environment:
    Reads configuration from the existing .env file via `app.config.settings`.
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Ensure we can import from the `app` package when script executed from repo root
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# Load environment variables before importing settings
load_dotenv()

from app.config import settings  # noqa: E402  pylint: disable=wrong-import-position
from app.core.database import (  # noqa: E402  pylint: disable=wrong-import-position
    create_database_if_not_exists,
    init_database,
)
from app.models.website import Website  # noqa: E402  pylint: disable=wrong-import-position
from app.models.user import User  # noqa: E402  pylint: disable=wrong-import-position
from app.models.collection import (  # noqa: E402  pylint: disable=wrong-import-position
    Collection,
    CollectionUser,
)
from app.models.system_prompt import SystemPrompt  # noqa: E402  pylint: disable=wrong-import-position
from app.models.activity_stats import ActivityStats  # noqa: E402  pylint: disable=wrong-import-position


LOGGER = logging.getLogger("initialize_schema")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_WEBSITE_DOMAIN = "localhost"
DEFAULT_WEBSITE_NAME = "Default Organization"
DEFAULT_COLLECTION_ID = "col_default"
DEFAULT_COLLECTION_NAME = "Default Collection"


def _ensure_database() -> None:
    LOGGER.info("Ensuring database exists and schema is up to date...")
    create_database_if_not_exists()
    init_database()


def _get_db_session():
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, SessionLocal()


def _perform_schema_migrations(engine) -> None:
    """Apply lightweight schema tweaks required for the latest application code."""
    inspector = inspect(engine)

    try:
        if not inspector.has_table("file_metadata"):
            LOGGER.info("Table 'file_metadata' not present yet; skipping column checks")
            return
    except SQLAlchemyError as exc:
        LOGGER.warning("Unable to inspect existing tables: %s", exc)
        return

    columns = {column["name"]: column for column in inspector.get_columns("file_metadata")}

    # Ensure file_content column exists for database-backed storage
    if "file_content" not in columns:
        LOGGER.info("Adding 'file_content' column to 'file_metadata' table")
        try:
            with engine.connect() as connection:
                connection.execute(text("ALTER TABLE file_metadata ADD COLUMN file_content LONGBLOB NULL"))
            LOGGER.info("'file_content' column created successfully")
        except SQLAlchemyError as exc:
            LOGGER.error("Failed to add 'file_content' column: %s", exc)
            raise
    else:
        LOGGER.info("'file_content' column already present")

    # Ensure file_path allows NULL now that content can live in the database
    file_path_meta = columns.get("file_path")
    if file_path_meta and not file_path_meta.get("nullable", False):
        LOGGER.info("Making 'file_path' column nullable to support DB-backed storage")
        try:
            with engine.connect() as connection:
                connection.execute(text("ALTER TABLE file_metadata MODIFY COLUMN file_path VARCHAR(500) NULL"))
            LOGGER.info("'file_path' column updated to allow NULL values")
        except SQLAlchemyError as exc:
            LOGGER.error("Failed to alter 'file_path' column nullability: %s", exc)
            raise


def _ensure_default_website(db) -> Website:
    website = (
        db.query(Website)
        .filter(Website.domain == DEFAULT_WEBSITE_DOMAIN)
        .first()
    )
    if website:
        LOGGER.info("Website '%s' already present (id=%s)", website.name, website.website_id)
        return website

    website = Website(
        name=DEFAULT_WEBSITE_NAME,
        domain=DEFAULT_WEBSITE_DOMAIN,
        description="Default organization for initial setup",
        admin_email="admin@chatbot.local",
        is_active=True,
        max_users=100,
        max_files=1000,
        max_storage_mb=10240,
    )
    db.add(website)
    db.flush()
    LOGGER.info("Created default website '%s' (id=%s)", website.name, website.website_id)
    return website


def _ensure_user(db, *, username: str, email: str, password: str, full_name: str,
                 role: str, website_id: str | None) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user:
        updated = False
        if user.role != role:
            user.role = role
            updated = True
        if user.website_id != website_id:
            user.website_id = website_id
            updated = True
        if updated:
            LOGGER.info("Updated existing user '%s' to role '%s'", username, role)
        else:
            LOGGER.info("User '%s' already exists", username)
        return user

    user = User(
        username=username,
        email=email,
        password_hash=PASSWORD_CONTEXT.hash(password),
        full_name=full_name,
        role=role,
        website_id=website_id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    LOGGER.info("Created user '%s' with role '%s'", username, role)
    return user


def _ensure_default_collection(db, website: Website, admin_user: User) -> Collection:
    collection = (
        db.query(Collection)
        .filter(Collection.collection_id == DEFAULT_COLLECTION_ID)
        .first()
    )
    if collection:
        LOGGER.info(
            "Collection '%s' already exists (id=%s)",
            collection.name,
            collection.collection_id,
        )
    else:
        collection = Collection(
            collection_id=DEFAULT_COLLECTION_ID,
            name=DEFAULT_COLLECTION_NAME,
            description="Default collection automatically created during setup",
            website_id=website.website_id,
            website_url="https://localhost/",
            admin_user_id=admin_user.user_id,
            admin_email=admin_user.email,
            is_active=True,
        )
        db.add(collection)
        db.flush()
        LOGGER.info(
            "Created default collection '%s' (id=%s)",
            collection.name,
            collection.collection_id,
        )

    assignment = (
        db.query(CollectionUser)
        .filter(
            CollectionUser.collection_id == collection.collection_id,
            CollectionUser.user_id == admin_user.user_id,
        )
        .first()
    )
    if not assignment:
        assignment = CollectionUser(
            collection_id=collection.collection_id,
            user_id=admin_user.user_id,
            role="admin",
            can_upload=True,
            can_download=True,
            can_delete=True,
            assigned_by=admin_user.user_id,
        )
        db.add(assignment)
        LOGGER.info("Linked admin '%s' to collection '%s'", admin_user.username, collection.name)

    prompt = (
        db.query(SystemPrompt)
        .filter(
            SystemPrompt.collection_id == collection.collection_id,
            SystemPrompt.is_default.is_(True),
        )
        .first()
    )
    if not prompt:
        prompt = SystemPrompt(
            prompt_id=str(uuid.uuid4()),
            name=f"Default Prompt - {collection.name}",
            description="Default AI prompt for the initial collection",
            system_prompt=(
                "You are a helpful AI assistant. Answer questions based on the provided context."
            ),
            collection_id=collection.collection_id,
            website_id=website.website_id,
            is_default=True,
            is_active=True,
            model_name="claude-3-haiku-20240307",
            max_tokens=4000,
            temperature=0.7,
        )
        db.add(prompt)
        LOGGER.info("Created default prompt for collection '%s'", collection.name)

    return collection


def main() -> None:
    LOGGER.info("Starting schema initialization")
    _ensure_database()

    engine, db = _get_db_session()
    _perform_schema_migrations(engine)
    try:
        website = _ensure_default_website(db)

        super_admin = _ensure_user(
            db,
            username="superadmin",
            email="superadmin@chatbot.local",
            password="superadmin123",
            full_name="Super Administrator",
            role="super_admin",
            website_id=None,
        )

        admin_user = _ensure_user(
            db,
            username="admin",
            email="admin@chatbot.local",
            password="admin123",
            full_name="Website Administrator",
            role="user_admin",
            website_id=website.website_id,
        )

        _ensure_user(
            db,
            username="user",
            email="user@chatbot.local",
            password="user123",
            full_name="Regular User",
            role="user",
            website_id=website.website_id,
        )

        collection = _ensure_default_collection(db, website, admin_user)

        # Ensure activity stats row exists
        stats = db.query(ActivityStats).first()
        if not stats:
            stats = ActivityStats()
            db.add(stats)
            LOGGER.info("Created default activity statistics row")

        db.commit()
        LOGGER.info("Schema initialization complete")
        LOGGER.info("Default website: %s (id=%s)", website.name, website.website_id)
        LOGGER.info("Default collection: %s (id=%s)", collection.name, collection.collection_id)
        LOGGER.info("Default accounts: superadmin/superadmin123, admin/admin123, user/user123")
    except Exception:
        db.rollback()
        LOGGER.exception("Schema initialization failed")
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
