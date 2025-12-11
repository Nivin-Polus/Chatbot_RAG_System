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
from app.models.plugin_integration import PluginIntegration
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
DEFAULT_PLUGIN_URL = "https://localhost/"


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
        if "plugin_token" not in user_columns:
            LOGGER.info("Adding 'plugin_token' column to 'users'")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN plugin_token TEXT NULL"))

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

    if "file_type" in columns:
        LOGGER.info("Ensuring 'file_type' column supports full MIME types")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE file_metadata MODIFY COLUMN file_type VARCHAR(255) NOT NULL"))

    if "mime_type" in columns:
        LOGGER.info("Ensuring 'mime_type' column supports full MIME types")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE file_metadata MODIFY COLUMN mime_type VARCHAR(255) NULL"))

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

    # Ensure plugin integrations table exists (created via ORM metadata). Nothing else yet.

    # Add crawler_jobs table if missing
    if not inspector.has_table("crawler_jobs"):
        LOGGER.info("Creating 'crawler_jobs' table...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE crawler_jobs (
                    job_id VARCHAR(36) PRIMARY KEY,
                    collection_id VARCHAR(36) NOT NULL,
                    user_id VARCHAR(36) NOT NULL,
                    target_url VARCHAR(2048) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    pages_discovered INT DEFAULT 0,
                    pages_crawled INT DEFAULT 0,
                    pages_skipped INT DEFAULT 0,
                    pages_failed INT DEFAULT 0,
                    chunks_created INT DEFAULT 0,
                    total_characters INT DEFAULT 0,
                    content_hash VARCHAR(64) NULL,
                    chunks_added INT DEFAULT 0,
                    chunks_updated INT DEFAULT 0,
                    chunks_deleted INT DEFAULT 0,
                    current_url VARCHAR(2048) NULL,
                    config JSON NULL,
                    is_scheduled TINYINT(1) DEFAULT 0,
                    schedule_interval_hours FLOAT NULL,
                    next_run_at DATETIME NULL,
                    last_successful_run DATETIME NULL,
                    run_count INT DEFAULT 0,
                    error_message TEXT NULL,
                    consecutive_failures INT DEFAULT 0,
                    crawled_urls JSON NULL,
                    failed_urls JSON NULL,
                    skipped_urls JSON NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    started_at DATETIME NULL,
                    completed_at DATETIME NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_crawler_jobs_collection (collection_id),
                    INDEX idx_crawler_jobs_user (user_id),
                    INDEX idx_crawler_jobs_status (status),
                    INDEX idx_crawler_jobs_scheduled (is_scheduled),
                    INDEX idx_crawler_jobs_next_run (next_run_at),
                    FOREIGN KEY (collection_id) REFERENCES collections(collection_id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """))
            conn.commit()
        LOGGER.info("Created 'crawler_jobs' table")
    else:
        # Migrate existing crawler_jobs table to add missing columns
        _migrate_crawler_jobs_table(engine, inspector)

    # Add chat_message_history table if missing
    if not inspector.has_table("chat_message_history"):
        LOGGER.info("Creating 'chat_message_history' table...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE chat_message_history (
                    message_id VARCHAR(36) PRIMARY KEY,
                    original_message_id VARCHAR(100) NULL,
                    session_id VARCHAR(36) NOT NULL,
                    collection_id VARCHAR(50) NULL,
                    user_id VARCHAR(36) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    sources JSON NULL,
                    message_timestamp DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_order INT NULL,
                    INDEX idx_chat_message_history_session (session_id),
                    INDEX idx_chat_message_history_collection (collection_id),
                    INDEX idx_chat_message_history_user (user_id),
                    INDEX idx_chat_message_history_created (created_at),
                    INDEX idx_chat_message_history_timestamp (message_timestamp),
                    INDEX idx_chat_message_history_order (message_order),
                    INDEX idx_chat_message_history_original_id (original_message_id),
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                    FOREIGN KEY (collection_id) REFERENCES collections(collection_id) ON DELETE SET NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """))
            conn.commit()
        LOGGER.info("Created 'chat_message_history' table")
    else:
        # Migrate existing chat_message_history table to add missing columns
        _migrate_chat_message_history_table(engine, inspector)


def _migrate_chat_message_history_table(engine, inspector):
    """Migrate existing chat_message_history table to add missing columns"""
    try:
        if not inspector.has_table("chat_message_history"):
            return
        
        existing_columns = {col["name"] for col in inspector.get_columns("chat_message_history")}
        alterations = []
        
        # Add missing columns
        if "original_message_id" not in existing_columns:
            alterations.append("ADD COLUMN original_message_id VARCHAR(100) NULL")
        if "message_timestamp" not in existing_columns:
            alterations.append("ADD COLUMN message_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
        if "message_order" not in existing_columns:
            alterations.append("ADD COLUMN message_order INT NULL")
        
        if alterations:
            LOGGER.info("Migrating 'chat_message_history' table: adding missing columns...")
            alter_statement = "ALTER TABLE chat_message_history " + ", ".join(alterations)
            with engine.connect() as conn:
                conn.execute(text(alter_statement))
                conn.commit()
            LOGGER.info(f"✅ Added {len(alterations)} columns to 'chat_message_history' table")
        
        # Add missing indexes
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("chat_message_history")}
        index_additions = []
        
        if "idx_chat_message_history_timestamp" not in existing_indexes:
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE INDEX idx_chat_message_history_timestamp ON chat_message_history(message_timestamp)"))
                    conn.commit()
                index_additions.append("idx_chat_message_history_timestamp")
            except Exception as e:
                LOGGER.warning(f"Could not create index idx_chat_message_history_timestamp: {e}")
        
        if "idx_chat_message_history_order" not in existing_indexes:
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE INDEX idx_chat_message_history_order ON chat_message_history(message_order)"))
                    conn.commit()
                index_additions.append("idx_chat_message_history_order")
            except Exception as e:
                LOGGER.warning(f"Could not create index idx_chat_message_history_order: {e}")
        
        if "idx_chat_message_history_original_id" not in existing_indexes:
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE INDEX idx_chat_message_history_original_id ON chat_message_history(original_message_id)"))
                    conn.commit()
                index_additions.append("idx_chat_message_history_original_id")
            except Exception as e:
                LOGGER.warning(f"Could not create index idx_chat_message_history_original_id: {e}")
        
        if index_additions:
            LOGGER.info(f"✅ Added {len(index_additions)} indexes to 'chat_message_history' table")
            
    except Exception as e:
        LOGGER.error(f"Failed to migrate chat_message_history table: {e}")
        # Don't raise - allow script to continue


def _migrate_crawler_jobs_table(engine, inspector):
    """Migrate existing crawler_jobs table to add missing columns"""
    try:
        if not inspector.has_table("crawler_jobs"):
            return
        
        existing_columns = {col["name"] for col in inspector.get_columns("crawler_jobs")}
        alterations = []
        
        # Add missing columns
        if "content_hash" not in existing_columns:
            alterations.append("ADD COLUMN content_hash VARCHAR(64) NULL")
        if "chunks_added" not in existing_columns:
            alterations.append("ADD COLUMN chunks_added INT DEFAULT 0")
        if "chunks_updated" not in existing_columns:
            alterations.append("ADD COLUMN chunks_updated INT DEFAULT 0")
        if "chunks_deleted" not in existing_columns:
            alterations.append("ADD COLUMN chunks_deleted INT DEFAULT 0")
        if "is_scheduled" not in existing_columns:
            alterations.append("ADD COLUMN is_scheduled TINYINT(1) DEFAULT 0")
        if "schedule_interval_hours" not in existing_columns:
            alterations.append("ADD COLUMN schedule_interval_hours FLOAT NULL")
        if "next_run_at" not in existing_columns:
            alterations.append("ADD COLUMN next_run_at DATETIME NULL")
        if "last_successful_run" not in existing_columns:
            alterations.append("ADD COLUMN last_successful_run DATETIME NULL")
        if "run_count" not in existing_columns:
            alterations.append("ADD COLUMN run_count INT DEFAULT 0")
        if "consecutive_failures" not in existing_columns:
            alterations.append("ADD COLUMN consecutive_failures INT DEFAULT 0")
        if "crawled_urls" not in existing_columns:
            alterations.append("ADD COLUMN crawled_urls JSON NULL")
        if "failed_urls" not in existing_columns:
            alterations.append("ADD COLUMN failed_urls JSON NULL")
        if "skipped_urls" not in existing_columns:
            alterations.append("ADD COLUMN skipped_urls JSON NULL")
        
        if alterations:
            LOGGER.info("Migrating 'crawler_jobs' table: adding missing columns...")
            alter_statement = "ALTER TABLE crawler_jobs " + ", ".join(alterations)
            with engine.connect() as conn:
                conn.execute(text(alter_statement))
                conn.commit()
            LOGGER.info(f"✅ Added {len(alterations)} columns to 'crawler_jobs' table")
        
        # Add missing indexes
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("crawler_jobs")}
        index_additions = []
        
        if "idx_crawler_jobs_scheduled" not in existing_indexes:
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE INDEX idx_crawler_jobs_scheduled ON crawler_jobs(is_scheduled)"))
                    conn.commit()
                index_additions.append("idx_crawler_jobs_scheduled")
            except Exception as e:
                LOGGER.warning(f"Could not create index idx_crawler_jobs_scheduled: {e}")
        
        if "idx_crawler_jobs_next_run" not in existing_indexes:
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE INDEX idx_crawler_jobs_next_run ON crawler_jobs(next_run_at)"))
                    conn.commit()
                index_additions.append("idx_crawler_jobs_next_run")
            except Exception as e:
                LOGGER.warning(f"Could not create index idx_crawler_jobs_next_run: {e}")
        
        if index_additions:
            LOGGER.info(f"✅ Added {len(index_additions)} indexes to 'crawler_jobs' table")
            
    except Exception as e:
        LOGGER.error(f"Failed to migrate crawler_jobs table: {e}")
        # Don't raise - allow script to continue


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

    _ensure_default_plugin_integration(db, collection, admin_user)

    return collection


def _normalize_url(raw_url: str) -> str:
    if not raw_url:
        return ""

    candidate = raw_url.strip()
    if not candidate:
        return ""

    from urllib.parse import urlparse

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


def _ensure_default_plugin_integration(db, collection: Collection, creator: User | None) -> None:
    existing_plugin = (
        db.query(PluginIntegration)
        .filter(PluginIntegration.collection_id == collection.collection_id)
        .first()
    )

    if existing_plugin:
        LOGGER.info("Plugin integration already exists for collection '%s'", collection.collection_id)
        return

    normalized = _normalize_url(collection.website_url or DEFAULT_PLUGIN_URL)
    if not normalized:
        LOGGER.warning(
            "Skipping default plugin integration for collection '%s' due to invalid URL",
            collection.collection_id,
        )
        return

    duplicate_plugin = (
        db.query(PluginIntegration)
        .filter(PluginIntegration.normalized_url == normalized)
        .first()
    )
    if duplicate_plugin:
        LOGGER.warning(
            "Skipping plugin integration for collection '%s' because URL '%s' is already linked to collection '%s'",
            collection.collection_id,
            normalized,
            duplicate_plugin.collection_id,
        )
        return

    plugin = PluginIntegration(
        collection_id=collection.collection_id,
        website_url=collection.website_url or DEFAULT_PLUGIN_URL,
        normalized_url=normalized,
        display_name=f"{collection.name} Plugin",
        is_active=True,
        created_by=creator.user_id if creator else None,
    )
    db.add(plugin)
    LOGGER.info("Created default plugin integration for collection '%s'", collection.collection_id)


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

        _ensure_user(
            db,
            username="pluginuser",
            email="pluginuser@chatbot.local",
            password="plugin123",
            full_name="Plugin Integrations",
            role="plugin_user",
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
