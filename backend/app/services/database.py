import sqlite3
from typing import Optional, List, Tuple, Dict, Any
from ..config import settings
from ..models.schemas import Incident

def get_db_connection() -> sqlite3.Connection:
    """Get read-only SQLite connection with row factory and busy timeout."""
    conn = sqlite3.connect(f"file:{settings.DATABASE_PATH}?mode=ro", uri=True, timeout=5.0)
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn

def row_to_incident(row: sqlite3.Row) -> Incident:
    """Convert an SQLite Row from CrashFrames to Incident model."""
    camera_id = int(row["camera_id"])
    frame_id = int(row["frame_id"])
    canonical_id = f"{camera_id}_{frame_id}"
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
    )

def query_recent_incidents(limit: int = 10) -> List[Incident]:
    """Retrieve the newest incidents (matching RunGui.py recent button)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time
            FROM CrashFrames
            ORDER BY crash_time DESC, rowid DESC
            LIMIT ?
        """
        rows = cursor.execute(query, (limit,)).fetchall()
        return [row_to_incident(r) for r in rows]
    finally:
        conn.close()

def query_incidents(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    limit: int = 20,
    cursor: Optional[int] = None,
) -> Tuple[List[Incident], Optional[int], bool]:
    """
    Search incidents with date, time, city, district filters and cursor pagination.
    Cursor pagination uses `rowid < cursor` on reverse chronological order.
    """
    conditions: List[str] = []
    params: List[Any] = []

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
        SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time
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
        # Case 1: Composite key e.g. 1528_76
        if "_" in identifier:
            parts = identifier.split("_", 1)
            if parts[0].isdigit() and parts[1].isdigit():
                cam_id = int(parts[0])
                frame_id = int(parts[1])
                row = cursor.execute("""
                    SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time
                    FROM CrashFrames
                    WHERE camera_id = ? AND frame_id = ?
                    ORDER BY rowid DESC
                    LIMIT 1
                """, (cam_id, frame_id)).fetchone()
                if row:
                    return row_to_incident(row)

        # Case 2: Integer rowid or camera_id
        if identifier.isdigit():
            row_id_val = int(identifier)
            row = cursor.execute("""
                SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time
                FROM CrashFrames
                WHERE rowid = ?
                LIMIT 1
            """, (row_id_val,)).fetchone()
            if row:
                return row_to_incident(row)

            # Fallback check if it was just camera_id
            row = cursor.execute("""
                SELECT rowid, camera_id, frame_id, from_no, city, district, crash_time
                FROM CrashFrames
                WHERE camera_id = ?
                ORDER BY crash_time DESC, rowid DESC
                LIMIT 1
            """, (row_id_val,)).fetchone()
            if row:
                return row_to_incident(row)

        return None
    finally:
        conn.close()
