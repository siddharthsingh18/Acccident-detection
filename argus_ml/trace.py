import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("argus.ml.trace")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRACES_DIR = PROJECT_ROOT / "artifacts" / "traces"


def is_trace_enabled() -> bool:
    """Return True if ARGUS_TRACE environment variable is enabled."""
    return os.getenv("ARGUS_TRACE", "false").lower() in ("true", "1", "yes")


def get_trace_dir() -> Path:
    """Return trace destination directory from ARGUS_TRACE_DIR or default."""
    trace_dir = Path(os.getenv("ARGUS_TRACE_DIR", str(DEFAULT_TRACES_DIR)))
    trace_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir


def sanitize_run_id(run_id: str) -> str:
    """Sanitize run_id into a safe filename without path traversal."""
    cleaned = Path(run_id).name.replace("..", "_").replace("/", "_").replace("\\", "_")
    return cleaned if cleaned else "default"


def record_batch_trace(run_id: str, record: Dict[str, Any]) -> None:
    """
    Append one JSON line representing a single 30-frame batch execution to
    artifacts/traces/<run_id>.jsonl. Strictly serializable, no image buffers.
    """
    if not is_trace_enabled():
        return

    try:
        clean_id = sanitize_run_id(run_id)
        trace_file = get_trace_dir() / f"{clean_id}.jsonl"

        # Ensure no raw numpy arrays or non-serializable objects
        safe_record: Dict[str, Any] = {}
        for k, v in record.items():
            if hasattr(v, "item"):
                safe_record[k] = v.item()
            elif isinstance(v, (int, float, str, bool)) or v is None:
                safe_record[k] = v
            elif isinstance(v, list):
                safe_record[k] = [x.item() if hasattr(x, "item") else x for x in v if not hasattr(x, "shape")]
            else:
                safe_record[k] = str(v)

        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(safe_record) + "\n")
    except Exception as e:
        logger.debug(f"Failed to write trace record for {run_id}: {e}")


def read_run_trace(run_id: str) -> List[Dict[str, Any]]:
    """Read all trace records from artifacts/traces/<run_id>.jsonl."""
    clean_id = sanitize_run_id(run_id)
    trace_file = get_trace_dir() / f"{clean_id}.jsonl"
    if not trace_file.exists():
        return []

    records = []
    with open(trace_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def summarize_run_trace(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarize a collection of batch trace records for a single video run.
    Identifies max trackers, total pairs evaluated, dominant filter dropping candidates,
    max classifier score, alert count, and the primary cause code.
    """
    if not records:
        return {
            "total_batches": 0,
            "max_trackers": 0,
            "total_pairs_evaluated": 0,
            "filter_counts": {},
            "dominant_filter": "NONE",
            "max_classifier_score": 0.0,
            "alert_count": 0,
            "primary_cause": "NO_TRACE",
        }

    total_batches = len(records)
    max_trackers = max(r.get("num_trackers", 0) for r in records)
    total_pairs = sum(r.get("pairs_evaluated", 0) for r in records)
    alert_count = sum(1 for r in records if r.get("decision", False))

    filter_counts = {
        "TOO_FAR": sum(r.get("failed_distance", 0) for r in records),
        "BELOW_SPEED": sum(r.get("failed_speed", 0) for r in records),
        "NO_DEVIATION": sum(r.get("failed_deviation", 0) for r in records),
        "BOX_TOO_SMALL": sum(r.get("failed_box_size", 0) for r in records),
        "ASPECT_RATIO": sum(r.get("failed_aspect_ratio", 0) for r in records),
    }

    # Find which filter dropped candidates most often
    sorted_filters = sorted(filter_counts.items(), key=lambda kv: kv[1], reverse=True)
    dominant_filter = sorted_filters[0][0] if sorted_filters and sorted_filters[0][1] > 0 else "NONE"

    # Max score
    scores = [r.get("classifier_score") for r in records if r.get("classifier_score") is not None]
    max_score = max(scores) if scores else 0.0

    # Assign primary cause code if no alert was raised
    if alert_count > 0:
        primary_cause = "CRASH_DETECTED"
    elif max_trackers == 0:
        primary_cause = "NO_DETECTIONS"
    elif max_trackers == 1:
        primary_cause = "SINGLE_VEHICLE"
    elif any(r.get("failed_box_size", 0) > 0 for r in records):
        primary_cause = "BOX_TOO_SMALL"
    elif any(r.get("classifier_score", 0.0) is not None and r.get("classifier_score", 0.0) > 0 for r in records):
        primary_cause = "CLASSIFIER_LOW_SCORE"
    elif filter_counts["TOO_FAR"] > 0 and filter_counts["TOO_FAR"] >= filter_counts["BELOW_SPEED"]:
        primary_cause = "TOO_FAR"
    elif filter_counts["BELOW_SPEED"] > 0:
        primary_cause = "BELOW_SPEED"
    else:
        primary_cause = "OTHER"

    return {
        "total_batches": total_batches,
        "max_trackers": max_trackers,
        "total_pairs_evaluated": total_pairs,
        "filter_counts": filter_counts,
        "dominant_filter": dominant_filter,
        "max_classifier_score": round(max_score, 4),
        "alert_count": alert_count,
        "primary_cause": primary_cause,
    }

