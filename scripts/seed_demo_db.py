#!/usr/bin/env python3
"""
Seed script for Argus SQLite database.
Idempotently initializes schema and seeds demo incident records if database is empty.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "System" / "Database" / "Argus_DB.db"
DEFAULT_SEED_FILE = ROOT_DIR / "scripts" / "data" / "demo_incidents.json"


def init_db(db_path: Path, seed_file: Path, force_seed: bool = False):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SavedFrames (
            camera_id INTEGER,
            frame_id INTEGER,
            CONSTRAINT "unique camera_id,frame_id" UNIQUE (camera_id ASC, frame_id ASC) ON CONFLICT REPLACE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CrashFrames (
            camera_id INTEGER,
            frame_id INTEGER,
            from_no INTEGER,
            city TEXT,
            district TEXT,
            crash_time TEXT,
            review_status TEXT DEFAULT NULL,
            review_note TEXT DEFAULT NULL,
            reviewed_at TEXT DEFAULT NULL,
            CONSTRAINT "unique_camera_id_and_frame_id" UNIQUE (camera_id ASC, frame_id ASC) ON CONFLICT REPLACE
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_crashframes_review_status ON CrashFrames(review_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_crashframes_time ON CrashFrames(crash_time)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Seed default settings if empty
    defaults = {
        "alert_sound_enabled": "false",
        "siren_volume": "80",
        "clip_retention_days": "30",
        "min_alert_confidence": "0.5",
    }
    for key, val in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, val),
        )

    # Check incident count
    count = cursor.execute("SELECT count(*) FROM CrashFrames").fetchone()[0]
    if (count == 0 or force_seed) and seed_file.exists():
        with open(seed_file, "r") as f:
            incidents = json.load(f)

        for inc in incidents:
            cursor.execute("""
                INSERT OR REPLACE INTO CrashFrames (
                    camera_id, frame_id, from_no, city, district, crash_time,
                    review_status, review_note, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inc.get("camera_id"),
                inc.get("frame_id"),
                inc.get("from_no", 5),
                inc.get("city", "Alexandria"),
                inc.get("district", "District 1"),
                inc.get("crash_time", "2021-01-07 09:39:31"),
                inc.get("review_status"),
                inc.get("review_note"),
                inc.get("reviewed_at"),
            ))
        print(f"✓ Seeded {len(incidents)} demo incidents into {db_path}")
    else:
        print(f"Database already contains {count} incidents. Skipping seeding.")

    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Initialize and seed Argus SQLite database.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to database")
    parser.add_argument("--seed-file", type=Path, default=DEFAULT_SEED_FILE, help="Path to demo incidents JSON")
    parser.add_argument("--force", action="store_true", help="Force re-seeding even if records exist")
    args = parser.parse_args()

    init_db(args.db_path, args.seed_file, force_seed=args.force)


if __name__ == "__main__":
    main()
