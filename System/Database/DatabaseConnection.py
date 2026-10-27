import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Tuple, Dict, Any

from System.Data.CONSTANTS import *


class DatabaseConnection:
    """
    Robust SQLite database connection manager for Argus vision pipeline.
    Uses WAL journal mode, busy timeouts, connection context managers,
    and parameterized queries to guarantee database integrity and prevent SQL injection.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DATABASE_PATH
        self.conn = None
        self.cursor = None

    @contextmanager
    def connection(self):
        """Context manager providing an SQLite connection with WAL mode and busy timeout."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            yield conn
        finally:
            conn.close()

    def connect(self):
        """Legacy helper for manual connection management."""
        self.conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        self.cursor = self.conn.cursor()
        return self.conn

    def close(self):
        """Legacy helper to close active connection."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            self.cursor = None

    def execute(self, query: str, params: Tuple = ()):
        """Execute a parameterized query safely within a connection context."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()

    def insertSavedFramesVid(self, camera_id: int, starting_frame_id: int):
        """Insert frame tracking record with parameterized SQL."""
        query = "INSERT INTO SavedFrames (camera_id, frame_id) VALUES (?, ?)"
        self.execute(query, (int(camera_id), int(starting_frame_id)))

    def insertCrashFramesVid(
        self,
        camera_id: int,
        starting_frame_id: int,
        from_no: int,
        city: str,
        district_no: str
    ):
        """Insert crash incident record with parameterized SQL preventing SQL injection."""
        query = """
            INSERT INTO CrashFrames (camera_id, frame_id, from_no, city, district, crash_time)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """
        self.execute(
            query,
            (int(camera_id), int(starting_frame_id), int(from_no), str(city), str(district_no))
        )

    def updateCrashFramesVid(self, camera_id: int, starting_frame_id: int, from_no: int):
        """Update incident chunk number with parameterized SQL."""
        query = "UPDATE CrashFrames SET from_no = ? WHERE camera_id = ? AND frame_id = ?"
        self.execute(query, (int(from_no), int(camera_id), int(starting_frame_id)))

    def deleteCrashFramesVid(self):
        """Clean up completed crash records."""
        query = "DELETE FROM CrashFrames WHERE from_no >= 5"
        self.execute(query)

    def deleteSavedFramesVid(self, camera_id: int, starting_frame_id: int):
        """Remove saved frames record."""
        query = "DELETE FROM SavedFrames WHERE camera_id = ? AND frame_id = ?"
        self.execute(query, (int(camera_id), int(starting_frame_id)))

    def selectCrashFrames(self) -> List[Tuple]:
        """Fetch pending crash records where from_no < 5."""
        query = "SELECT camera_id, frame_id, from_no, city, district, crash_time FROM CrashFrames WHERE from_no < 5"
        with self.connection() as conn:
            return conn.cursor().execute(query).fetchall()

    def selectSavedFrames(self, camera_id: int, starting_frame_id: int) -> List[Tuple]:
        """Query future saved frames for camera feed stitching."""
        query = """
            SELECT frame_id FROM SavedFrames
            WHERE camera_id = ? AND frame_id > ?
            ORDER BY frame_id ASC
        """
        with self.connection() as conn:
            return conn.cursor().execute(query, (int(camera_id), int(starting_frame_id))).fetchall()

    def selectCrashFramesList(self, dic: Dict[str, Any]) -> List[Tuple]:
        """Query crashes matching dynamic criteria using parameterized WHERE clauses."""
        conditions = []
        params = []

        if CITY in dic and dic[CITY]:
            conditions.append("city = ?")
            params.append(str(dic[CITY]))

        if DISTRICT in dic and dic[DISTRICT]:
            conditions.append("district = ?")
            params.append(str(dic[DISTRICT]))

        if START_DATE in dic and dic[START_DATE]:
            start_date = str(dic[START_DATE])
            end_date = str(dic.get(END_DATE, start_date))
            start_time = str(dic.get(START_TIME, "00:00:00"))
            end_time = str(dic.get(END_TIME, "23:59:59"))

            start_ts = f"{start_date} {start_time}"
            end_ts = f"{end_date} {end_time}"
            conditions.append("crash_time BETWEEN ? AND ?")
            params.extend([start_ts, end_ts])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT camera_id, frame_id, city, district, crash_time
            FROM CrashFrames
            {where_clause}
            ORDER BY crash_time DESC
        """
        with self.connection() as conn:
            return conn.cursor().execute(query, tuple(params)).fetchall()

    def selectCrashFramesLast10(self) -> List[Tuple]:
        """Query last 10 crash events in reverse chronological order."""
        query = """
            SELECT camera_id, frame_id, city, district, crash_time
            FROM CrashFrames
            ORDER BY crash_time DESC
            LIMIT 10
        """
        with self.connection() as conn:
            return conn.cursor().execute(query).fetchall()
