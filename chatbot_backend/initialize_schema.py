#!/usr/bin/env python3
"""
Initializes the chatbot multi-tenant schema and inserts default data.

Run this script once on a fresh database.

Usage:
    python initialize_schema.py
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

# Ensure import path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

load_dotenv()

from app.config import settings
from app.core.database import create_database_if_not_exists, init_database
from app.models.website import Website
from app.models.user import User
from app.models.collection import Collection, CollectionUser
from app.models.system_prompt import SystemPrompt
from app.models.activity_stats import ActivityStats

LOGGER = logging.getLogger("initialize_schema")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
_BCRYPT_MAX_LENGTH = 72


def _prepare_password(password: str | bytes) -> str:
    if isinstance(password, bytes):
        password = password.decode("utf-8", errors="ignore")
    return (password or "")[:_BCRYPT_MAX_LENGTH]


def _hash_password(password: str) -> str:
    return PASSWORD_CONTEXT.hash(_prepare_password(password))


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
    inspector = inspect(engine)

    # Ensure essential tables expose the expected primary key columns before proceeding.
    if inspector.has_table("users"):
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "user_id" not in user_columns:
            LOGGER.critical(
                "Detected incompatible schema: existing 'users' table lacks the 'user_id' primary key column. "
                "The current ORM models (see `app/models/user.py`) require this column for foreign-key relationships. "
                "Please migrate the table (e.g., add a VARCHAR(36) 'user_id' primary key and update foreign keys) "
                "or drop/recreate the database before rerunning initialize_schema.py."
            )
            raise RuntimeError(
                "Incompatible schema detected: missing 'users.user_id' column. "
                "Apply a migration or recreate the database to align with the latest models."
            )
    try:
        if not inspector.has_table("file_metadata"):
            LOGGER.info("No 'file_metadata' table yet, skipping migrations")
            return
    except SQLAlchemyError as exc:
        LOGGER.warning("Could not inspect database: %s", exc)
        return

    columns = {col["name"]: col for col in inspector.get_columns("file_metadata")}
    if "file_content" not in columns:
        LOGGER.info("Adding 'file_content' column to 'file_metadata'")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE file_metadata ADD COLUMN file_content LONGBLOB NULL"))

    # Make 'file_path' nullable
    if "file_path" in columns and not columns["file_path"].get("nullable", False):
        LOGGER.info("Making 'file_path' column nullable")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE file_metadata MODIFY COLUMN file_path VARCHAR(500) NULL"))

    # Add optional prompt columns
    if inspector.has_table("system_prompts"):
        prompt_columns = {col["name"] for col in inspector.get_columns("system_prompts")}
        additions = {
            "user_prompt_template": "TEXT NULL DEFAULT ''",
            "context_template": "TEXT NULL DEFAULT ''",
            "vector_db_id": "VARCHAR(36) NULL DEFAULT NULL",
            "website_id": "VARCHAR(36) NULL DEFAULT NULL",
            "model_name": "VARCHAR(100) NOT NULL DEFAULT 'claude-3-haiku-20240307'",
            "max_tokens": "INT NOT NULL DEFAULT 1000",
            "temperature": "FLOAT NOT NULL DEFAULT 0",
            "usage_count": "INT NOT NULL DEFAULT 0",
            "last_used": "DATETIME NULL DEFAULT NULL",
        }
        for name, ddl in additions.items():
            if name not in prompt_columns:
                with engine.connect() as conn:
                    conn.execute(text(f"ALTER TABLE system_prompts ADD COLUMN {name} {ddl}"))
                LOGGER.info("Added column '%s' to system_prompts", name)


def _ensure_default_website(db) -> Website:
    website = db.query(Website).filter_by(domain=DEFAULT_WEBSITE_DOMAIN).first()
    if website:
        LOGGER.info("Website '%s' already exists", website.name)
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
    LOGGER.info("Created default website '%s'", website.name)
    return website


def _ensure_user(
    db,
    *,
    username: str,
    email: str,
    password: str,
    full_name: str,
    role: str,
    website_id: str | None,
) -> User:
    user = db.query(User).filter_by(username=username).first()
    if user:
        if user.role != role or user.website_id != website_id:
            user.role = role
            user.website_id = website_id
            LOGGER.info("Updated user '%s' role or website", username)
        else:
            LOGGER.info("User '%s' already exists", username)
        return user

    user = User(
        username=username,
        email=email,
        password_hash=_hash_password(password),
        full_name=full_name,
        role=role,
        website_id=website_id,  # <-- FIXED: passing value, not Column
        is_active=True,
    )
    db.add(user)
    db.flush()
    LOGGER.info("Created user '%s' with role '%s'", username, role)
    return user


def _ensure_default_collection(db, website: Website, admin_user: User) -> Collection:
    collection = db.query(Collection).filter_by(collection_id=DEFAULT_COLLECTION_ID).first()
    if not collection:
        collection = Collection(
            collection_id=DEFAULT_COLLECTION_ID,
            name=DEFAULT_COLLECTION_NAME,
            description="Default collection created during setup",
            website_id=website.website_id,
            website_url="https://localhost/",
            admin_user_id=admin_user.user_id,
            admin_email=admin_user.email,
            is_active=True,
        )
        db.add(collection)
        db.flush()
        LOGGER.info("Created default collection '%s'", collection.name)

    link = (
        db.query(CollectionUser)
        .filter_by(collection_id=collection.collection_id, user_id=admin_user.user_id)
        .first()
    )
    if not link:
        db.add(
            CollectionUser(
                collection_id=collection.collection_id,
                user_id=admin_user.user_id,
                role="admin",
                can_upload=True,
                can_download=True,
                can_delete=True,
                assigned_by=admin_user.user_id,
            )
        )
        LOGGER.info("Linked admin '%s' to collection '%s'", admin_user.username, collection.name)

    prompt = (
        db.query(SystemPrompt)
        .filter_by(collection_id=collection.collection_id, is_default=True)
        .first()
    )
    if not prompt:
        db.add(
            SystemPrompt(
                prompt_id=str(uuid.uuid4()),
                name=f"Default Prompt - {collection.name}",
                description="Default AI prompt for initial collection",
                system_prompt="You are a helpful AI assistant. Answer questions based on the provided context.",
                collection_id=collection.collection_id,
                website_id=website.website_id,
                is_default=True,
                is_active=True,
                model_name="claude-3-haiku-20240307",
                max_tokens=4000,
                temperature=0.7,
            )
        )
        LOGGER.info("Created default prompt for collection '%s'", collection.name)

    return collection


def main() -> None:
    LOGGER.info("Starting schema initialization...")
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

        _ensure_default_collection(db, website, admin_user)

        if not db.query(ActivityStats).first():
            db.add(ActivityStats())
            LOGGER.info("Created default ActivityStats record")

        db.commit()
        LOGGER.info("✅ Schema initialization complete!")
    except Exception:
        db.rollback()
        LOGGER.exception("Schema initialization failed")
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
