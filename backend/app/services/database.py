from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Optional, List, Tuple, Dict, Any
from ..config import settings
from ..models.schemas import Incident, SystemSettings, UpdateSettingsRequest

def get_db_connection() -> sqlite3.Connection:
    """Get read-only SQLite connection with row factory and busy timeout."""
    conn = sqlite3.connect(f"file:{settings.DATABASE_PATH}?mode=ro", uri=True, timeout=5.0)
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn

def get_write_connection(timeout: float = 5.0) -> sqlite3.Connection:
    """Get read-write SQLite connection with row factory, busy timeout, and WAL mode."""
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=timeout)
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def apply_migrations(db_path: Optional[str] = None) -> None:
    """
    Idempotently apply database schema migrations.
    Safely checks table/column presence before executing ALTER TABLE or CREATE.
    Never drops or deletes existing data.
    """
    target_path = Path(db_path) if db_path else settings.DATABASE_PATH
    if not target_path.exists():
        return

    conn = sqlite3.connect(target_path, timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")

        cursor = conn.cursor()
        existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(CrashFrames);").fetchall()}

        if "review_status" not in existing_cols:
            cursor.execute("ALTER TABLE CrashFrames ADD COLUMN review_status TEXT DEFAULT NULL;")
        if "review_note" not in existing_cols:
            cursor.execute("ALTER TABLE CrashFrames ADD COLUMN review_note TEXT DEFAULT NULL;")
        if "reviewed_at" not in existing_cols:
            cursor.execute("ALTER TABLE CrashFrames ADD COLUMN reviewed_at TEXT DEFAULT NULL;")

        # Indexes & View
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crashframes_review_status ON CrashFrames(review_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crashframes_time ON CrashFrames(crash_time);")
        cursor.execute("CREATE VIEW IF NOT EXISTS incidents AS SELECT rowid, * FROM CrashFrames;")

        # Settings table migration (Phase 2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        now_iso = datetime.now(timezone.utc).isoformat()
        default_settings = [
            ("alert_sound_enabled", "false", now_iso),
            ("siren_volume", "80", now_iso),
            ("clip_retention_days", "30", now_iso),
            ("min_alert_confidence", "0.5", now_iso),
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?);
        """, default_settings)

        conn.commit()
    finally:
        conn.close()

def row_to_incident(row: sqlite3.Row) -> Incident:
    """Convert an SQLite Row from CrashFrames to Incident model."""
    camera_id = int(row["camera_id"])
    frame_id = int(row["frame_id"])
    canonical_id = f"{camera_id}_{frame_id}"
    keys = row.keys()
    return Incident(
        id=canonical_id,
        rowid=int(row["rowid"]),
        camera_id=camera_id,
        starting_frame_id=frame_id,
        city=row["city"],
        district=row["district"],
        crash_time=row["crash_time"],
        from_no=int(row["from_no"]) if row["from_no"] is not None else None,
        thumbnail_url=f"/media/thumbnails/{canonical_id}.jpg",
        video_url=f"/api/incidents/{canonical_id}/video",
        review_status=row["review_status"] if "review_status" in keys else None,
        review_note=row["review_note"] if "review_note" in keys else None,
        reviewed_at=row["reviewed_at"] if "reviewed_at" in keys else None,
    )

def query_recent_incidents(limit: int = 10) -> List[Incident]:
    """Retrieve the newest incidents (matching RunGui.py recent button)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time,
                   review_status, review_note, reviewed_at
            FROM CrashFrames
            ORDER BY crash_time DESC, rowid DESC
            LIMIT ?
        """
        rows = cursor.execute(query, (limit,)).fetchall()
        return [row_to_incident(r) for r in rows]
    finally:
        conn.close()

def query_incidents(
    camera_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 20,
    cursor: Optional[int] = None,
) -> Tuple[List[Incident], Optional[int], bool]:
    """
    Search incidents with camera_id, date, time, city, district, review_status filters and cursor pagination.
    Cursor pagination uses `rowid < cursor` on reverse chronological order.
    """
    conditions: List[str] = []
    params: List[Any] = []

    # Camera ID filter
    if camera_id is not None:
        conditions.append("camera_id = ?")
        params.append(camera_id)

    # Cursor condition
    if cursor is not None:
        conditions.append("rowid < ?")
        params.append(cursor)

    # City filter
    if city and city.strip():
        conditions.append("city LIKE ?")
        params.append(f"%{city.strip()}%")

    # District filter
    if district and district.strip():
        conditions.append("district LIKE ?")
        params.append(f"%{district.strip()}%")

    # Review status filter: 'unreviewed' | 'confirmed' | 'false_alarm'
    if review_status and review_status.strip():
        r_stat = review_status.strip().lower()
        if r_stat == "unreviewed":
            conditions.append("(review_status IS NULL OR review_status = '')")
        elif r_stat in ("confirmed", "false_alarm"):
            conditions.append("review_status = ?")
            params.append(r_stat)

    # Format date/time filters
    # Convert DD/MM/YYYY to YYYY-MM-DD if needed
    def normalize_date(d: str) -> str:
        d = d.strip()
        if "/" in d:
            parts = d.split("/")
            if len(parts) == 3:
                day, month, year = parts
                return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
        return d

    def normalize_time(t: str, default: str) -> str:
        t = t.strip()
        if not t:
            return default
        parts = t.split(":")
        if len(parts) == 2:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
        if len(parts) == 3:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return default

    # Date range filters
    if start_date or end_date:
        norm_start_date = normalize_date(start_date) if start_date else "1970-01-01"
        norm_end_date = normalize_date(end_date) if end_date else "2099-12-31"
        norm_start_time = normalize_time(start_time, "00:00:00") if start_time else "00:00:00"
        norm_end_time = normalize_time(end_time, "23:59:59") if end_time else "23:59:59"

        start_ts = f"{norm_start_date} {norm_start_time}"
        end_ts = f"{norm_end_date} {norm_end_time}"
        conditions.append("crash_time BETWEEN ? AND ?")
        params.extend([start_ts, end_ts])
    elif start_time or end_time:
        # Filter by time of day: strftime('%H:%M:%S', crash_time)
        norm_start_time = normalize_time(start_time, "00:00:00") if start_time else "00:00:00"
        norm_end_time = normalize_time(end_time, "23:59:59") if end_time else "23:59:59"
        conditions.append("time(crash_time) BETWEEN ? AND ?")
        params.extend([norm_start_time, norm_end_time])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time,
               review_status, review_note, reviewed_at
        FROM CrashFrames
        {where_clause}
        ORDER BY crash_time DESC, rowid DESC
        LIMIT ?
    """
    params.append(limit + 1)

    conn = get_db_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        has_more = len(rows) > limit
        result_rows = rows[:limit]
        incidents = [row_to_incident(r) for r in result_rows]
        next_cursor = incidents[-1].rowid if has_more and incidents else None
        return incidents, next_cursor, has_more
    finally:
        conn.close()

def query_incident_by_id(identifier: str) -> Optional[Incident]:
    """Lookup an incident by canonical id (camera_id_frame_id) or rowid."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        select_cols = """
            SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time,
                   review_status, review_note, reviewed_at
            FROM CrashFrames
        """
        # Case 1: Composite key e.g. 1528_76
        if "_" in identifier:
            parts = identifier.split("_", 1)
            if parts[0].isdigit() and parts[1].isdigit():
                cam_id = int(parts[0])
                frame_id = int(parts[1])
                row = cursor.execute(f"""
                    {select_cols}
                    WHERE camera_id = ? AND frame_id = ?
                    ORDER BY rowid DESC
                    LIMIT 1
                """, (cam_id, frame_id)).fetchone()
                if row:
                    return row_to_incident(row)

        # Case 2: Integer rowid or camera_id
        if identifier.isdigit():
            row_id_val = int(identifier)
            row = cursor.execute(f"""
                {select_cols}
                WHERE rowid = ?
                LIMIT 1
            """, (row_id_val,)).fetchone()
            if row:
                return row_to_incident(row)

            # Fallback check if it was just camera_id
            row = cursor.execute(f"""
                {select_cols}
                WHERE camera_id = ?
                ORDER BY crash_time DESC, rowid DESC
                LIMIT 1
            """, (row_id_val,)).fetchone()
            if row:
                return row_to_incident(row)

        return None
    finally:
        conn.close()

def update_incident_review(
    identifier: str,
    status: str,
    note: Optional[str] = None,
    reviewed_at: Optional[str] = None
) -> Optional[Incident]:
    """
    Update human verification status and review note for an incident.
    Returns the updated Incident or None if not found.
    """
    if reviewed_at is None:
        reviewed_at = datetime.now(timezone.utc).isoformat()

    conn = get_write_connection()
    try:
        cursor = conn.cursor()
        rowid_to_update = None

        if "_" in identifier:
            parts = identifier.split("_", 1)
            if parts[0].isdigit() and parts[1].isdigit():
                cam_id = int(parts[0])
                frame_id = int(parts[1])
                row = cursor.execute(
                    "SELECT rowid FROM CrashFrames WHERE camera_id = ? AND frame_id = ? ORDER BY rowid DESC LIMIT 1",
                    (cam_id, frame_id)
                ).fetchone()
                if row:
                    rowid_to_update = int(row["rowid"])

        if rowid_to_update is None and identifier.isdigit():
            row_id_val = int(identifier)
            row = cursor.execute("SELECT rowid FROM CrashFrames WHERE rowid = ? LIMIT 1", (row_id_val,)).fetchone()
            if row:
                rowid_to_update = int(row["rowid"])
            else:
                row = cursor.execute(
                    "SELECT rowid FROM CrashFrames WHERE camera_id = ? ORDER BY crash_time DESC, rowid DESC LIMIT 1",
                    (row_id_val,)
                ).fetchone()
                if row:
                    rowid_to_update = int(row["rowid"])

        if rowid_to_update is None:
            return None

        cursor.execute(
            """
            UPDATE CrashFrames
            SET review_status = ?, review_note = ?, reviewed_at = ?
            WHERE rowid = ?
            """,
            (status, note, reviewed_at, rowid_to_update)
        )
        conn.commit()

        # Fetch and return updated incident
        updated_row = cursor.execute(
            """
            SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time,
                   review_status, review_note, reviewed_at
            FROM CrashFrames
            WHERE rowid = ?
            """,
            (rowid_to_update,)
        ).fetchone()

        return row_to_incident(updated_row) if updated_row else None
    finally:
        conn.close()

def get_system_settings() -> SystemSettings:
    """Retrieve current system settings from SQLite database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT key, value, updated_at FROM settings;").fetchall()
        settings_map: Dict[str, str] = {row["key"]: row["value"] for row in rows}
        latest_updated_at = max((row["updated_at"] for row in rows), default=None)

        return SystemSettings(
            alert_sound_enabled=settings_map.get("alert_sound_enabled", "false").lower() in ("true", "1"),
            siren_volume=int(settings_map.get("siren_volume", 80)),
            clip_retention_days=int(settings_map.get("clip_retention_days", 30)),
            min_alert_confidence=float(settings_map.get("min_alert_confidence", 0.5)),
            updated_at=latest_updated_at,
        )
    finally:
        conn.close()

def update_system_settings(req: UpdateSettingsRequest) -> SystemSettings:
    """Update system settings with parameterized values and return updated model."""
    conn = get_write_connection()
    try:
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        records = [
            ("alert_sound_enabled", "true" if req.alert_sound_enabled else "false", now_iso),
            ("siren_volume", str(req.siren_volume), now_iso),
            ("clip_retention_days", str(req.clip_retention_days), now_iso),
            ("min_alert_confidence", str(req.min_alert_confidence), now_iso),
        ]
        cursor.executemany("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;
        """, records)
        conn.commit()

        return SystemSettings(
            alert_sound_enabled=req.alert_sound_enabled,
            siren_volume=req.siren_volume,
            clip_retention_days=req.clip_retention_days,
            min_alert_confidence=req.min_alert_confidence,
            updated_at=now_iso,
        )
    finally:
        conn.close()
