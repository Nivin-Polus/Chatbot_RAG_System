#!/usr/bin/env python3
"""Backfill CollectionUser rows for existing collection administrators.

Usage:
    python scripts/backfill_collection_access.py

This script assigns the `CollectionUser` role='admin' to any user who has been
marked as the `admin_user_id` for a collection but does not yet have an entry
in `collection_users`. It also grants `can_upload`, `can_download`, and
`can_delete` permissions.
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

load_dotenv()

from app.config import settings  # noqa: E402
from app.models.collection import Collection, CollectionUser  # noqa: E402
from app.models.user import User  # noqa: E402

LOGGER = logging.getLogger("backfill_collection_access")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def get_session():
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def backfill_collection_users():
    engine, db = get_session()
    try:
        collections = db.query(Collection).all()
        LOGGER.info("Processing %d collections", len(collections))

        created = 0
        for collection in collections:
            if not collection.admin_user_id:
                continue

            admin_user = db.query(User).filter(User.user_id == collection.admin_user_id).first()
            if not admin_user:
                LOGGER.warning(
                    "Collection %s (%s) has missing admin user %s",
                    collection.name,
                    collection.collection_id,
                    collection.admin_user_id,
                )
                continue

            assignment = (
                db.query(CollectionUser)
                .filter(
                    CollectionUser.collection_id == collection.collection_id,
                    CollectionUser.user_id == admin_user.user_id,
                )
                .first()
            )

            if assignment:
                continue

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
            created += 1
            LOGGER.info(
                "Assigned admin '%s' to collection '%s'",
                admin_user.username,
                collection.name,
            )

        if created:
            db.commit()
        LOGGER.info("Backfill completed. Added %d assignments", created)
    except Exception:
        db.rollback()
        LOGGER.exception("Backfill failed")
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    backfill_collection_users()
