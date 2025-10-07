#!/usr/bin/env python3
"""Migrate existing JSON-based activity logs into the database tables.

Usage:
    python scripts/migrate_activity_logs.py

This reads `activity_logs/activities.json` and `activity_logs/stats.json`,
inserting records into `activity_logs` and `activity_stats` tables.
Existing rows are preserved; duplicate activity_ids are skipped.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

load_dotenv()

from app.config import settings  # noqa: E402
from app.models.activity_log import ActivityLog  # noqa: E402
from app.models.activity_stats import ActivityStats  # noqa: E402
from app.models.user import User  # noqa: E402

LOGGER = logging.getLogger("migrate_activity_logs")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def get_session():
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def load_json_file(path: Path):
    if not path.exists():
        LOGGER.info("File %s not found; skipping", path)
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        LOGGER.error("Failed to parse %s: %s", path, exc)
        return None


def migrate_activity_logs(db, activities_path: Path):
    raw_activities = load_json_file(activities_path) or []
    if not raw_activities:
        LOGGER.info("No activities to migrate")
        return 0

    migrated = 0
    for entry in raw_activities:
        activity_id = entry.get("id")
        if not activity_id:
            LOGGER.warning("Skipping activity without id: %s", entry)
            continue

        existing = db.query(ActivityLog).filter(ActivityLog.activity_id == activity_id).first()
        if existing:
            continue

        username = entry.get("user", "unknown")
        user = db.query(User).filter(User.username == username).first()

        activity = ActivityLog.from_payload(
            activity_id=activity_id,
            activity_type=entry.get("type", "unknown"),
            username=username,
            user_id=user.user_id if user else None,
            details=entry.get("details"),
            metadata=entry.get("metadata"),
            created_at=datetime.fromisoformat(entry["timestamp"]) if entry.get("timestamp") else None,
        )

        db.add(activity)
        migrated += 1

    LOGGER.info("Migrated %d activity records", migrated)
    return migrated


def migrate_stats(db, stats_path: Path):
    raw_stats = load_json_file(stats_path)
    if raw_stats is None:
        return False

    stats = db.query(ActivityStats).first()
    created = False
    if not stats:
        stats = ActivityStats()
        created = True
        db.add(stats)

    stats.total_files_uploaded = raw_stats.get("total_files_uploaded", stats.total_files_uploaded)
    stats.total_chat_sessions = raw_stats.get("total_chat_sessions", stats.total_chat_sessions)
    stats.total_queries = raw_stats.get("total_queries", stats.total_queries)

    def parse_timestamp(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            LOGGER.warning("Invalid timestamp format: %s", value)
            return None

    stats.last_document_upload = parse_timestamp(raw_stats.get("last_document_upload")) or stats.last_document_upload
    stats.last_chat_session = parse_timestamp(raw_stats.get("last_chat_session")) or stats.last_chat_session
    stats.last_activity = parse_timestamp(raw_stats.get("last_activity")) or stats.last_activity

    LOGGER.info("Activity stats %s", "created" if created else "updated")
    return True


def main():
    storage_dir = BASE_DIR / "activity_logs"
    activities_path = storage_dir / "activities.json"
    stats_path = storage_dir / "stats.json"

    engine, db = get_session()
    try:
        migrated = migrate_activity_logs(db, activities_path)
        stats_updated = migrate_stats(db, stats_path)

        if migrated or stats_updated:
            db.commit()
            LOGGER.info("Migration complete")
        else:
            LOGGER.info("Nothing to migrate")
    except Exception:
        db.rollback()
        LOGGER.exception("Migration failed")
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
