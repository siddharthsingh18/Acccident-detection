import asyncio
import time
import shutil
import sqlite3
import subprocess
from typing import Dict, Any, Tuple
from ..config import settings
from ..models.schemas import ServiceHealth, HealthResponse

async def check_tcp_port(host: str, port: int, timeout: float = 0.3) -> Tuple[bool, float | None]:
    """Check if a TCP socket port is reachable within timeout seconds."""
    t0 = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        latency = (time.perf_counter() - t0) * 1000.0
        return True, round(latency, 2)
    except Exception:
        return False, None

def check_database() -> Dict[str, Any]:
    """Check SQLite database file accessibility and row count."""
    db_path = settings.DATABASE_PATH
    if not db_path.exists():
        return {
            "accessible": False,
            "path": str(db_path),
            "error": "Database file not found",
            "total_incidents": 0,
        }
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1.0)
        cursor = conn.cursor()
        count = cursor.execute("SELECT count(*) FROM CrashFrames;").fetchone()[0]
        conn.close()
        return {
            "accessible": True,
            "path": str(db_path),
            "total_incidents": count,
        }
    except Exception as e:
        return {
            "accessible": False,
            "path": str(db_path),
            "error": str(e),
            "total_incidents": 0,
        }

def check_ffmpeg() -> Dict[str, Any]:
    """Check whether ffmpeg executable is installed and get version."""
    path = shutil.which("ffmpeg")
    if not path:
        return {"available": False, "version": None}
    try:
        res = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=1.0)
        first_line = res.stdout.splitlines()[0] if res.stdout else "unknown"
        return {"available": True, "path": path, "version": first_line}
    except Exception as e:
        return {"available": True, "path": path, "error": str(e)}

async def get_system_health() -> HealthResponse:
    """Check health across all 4 Argus microservices, database, and ffmpeg."""
    services_to_check = [
        ("master", settings.ZMQ_HOST, settings.ZMQ_MASTER_PORT),
        ("detect", settings.ZMQ_HOST, settings.ZMQ_DETECT_PORT),
        ("tracker", settings.ZMQ_HOST, settings.ZMQ_TRACK_PORT),
        ("crash", settings.ZMQ_HOST, settings.ZMQ_CRASH_PORT),
    ]

    checks = await asyncio.gather(
        *(check_tcp_port(h, p) for _, h, p in services_to_check)
    )

    services: Dict[str, ServiceHealth] = {}
    reachable_count = 0

    for (name, host, port), (reachable, latency) in zip(services_to_check, checks):
        if reachable:
            reachable_count += 1
        services[name] = ServiceHealth(
            name=name,
            host=host,
            port=port,
            reachable=reachable,
            latency_ms=latency,
        )

    db_health = check_database()
    ffmpeg_health = check_ffmpeg()

    if reachable_count == len(services_to_check) and db_health["accessible"]:
        status = "ok"
    elif reachable_count > 0 or db_health["accessible"]:
        status = "degraded"
    else:
        status = "down"

    return HealthResponse(
        status=status,
        services=services,
        database=db_health,
        ffmpeg=ffmpeg_health,
    )
