import os
from pathlib import Path
import pytest
from argus_ml.trace import (
    is_trace_enabled,
    get_trace_dir,
    sanitize_run_id,
    record_batch_trace,
    read_run_trace,
    summarize_run_trace,
)


def test_is_trace_enabled_flag(monkeypatch):
    monkeypatch.delenv("ARGUS_TRACE", raising=False)
    assert not is_trace_enabled()

    monkeypatch.setenv("ARGUS_TRACE", "true")
    assert is_trace_enabled()

    monkeypatch.setenv("ARGUS_TRACE", "1")
    assert is_trace_enabled()

    monkeypatch.setenv("ARGUS_TRACE", "false")
    assert not is_trace_enabled()


def test_sanitize_run_id():
    assert sanitize_run_id("test_clip") == "test_clip"
    assert sanitize_run_id("../../etc/passwd") == "passwd"
    assert sanitize_run_id("dir/nested/file") == "file"
    assert sanitize_run_id("") == "default"


def test_record_and_read_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_TRACE", "true")
    monkeypatch.setenv("ARGUS_TRACE_DIR", str(tmp_path))

    record_1 = {
        "run_id": "clip_abc",
        "batch_index": 1,
        "starting_frame_id": 1,
        "num_detections": 3,
        "num_trackers": 3,
        "pairs_evaluated": 3,
        "failed_speed": 1,
        "failed_distance": 2,
        "failed_deviation": 0,
        "candidates_passed_geometry": 0,
        "failed_box_size": 0,
        "failed_aspect_ratio": 0,
        "classifier_score": 0.42,
        "decision": False,
        "primary_reason": "TOO_FAR",
    }
    record_2 = {
        "run_id": "clip_abc",
        "batch_index": 2,
        "starting_frame_id": 16,
        "num_detections": 3,
        "num_trackers": 3,
        "pairs_evaluated": 3,
        "failed_speed": 0,
        "failed_distance": 0,
        "failed_deviation": 0,
        "candidates_passed_geometry": 1,
        "failed_box_size": 0,
        "failed_aspect_ratio": 0,
        "classifier_score": 0.88,
        "decision": True,
        "primary_reason": "CRASH_DETECTED",
    }

    record_batch_trace("clip_abc", record_1)
    record_batch_trace("clip_abc", record_2)

    records = read_run_trace("clip_abc")
    assert len(records) == 2
    assert records[0]["run_id"] == "clip_abc"
    assert records[0]["classifier_score"] == 0.42
    assert records[1]["decision"] is True


def test_summarize_run_trace():
    records = [
        {
            "run_id": "test_clip",
            "batch_index": 1,
            "num_trackers": 4,
            "pairs_evaluated": 6,
            "failed_speed": 2,
            "failed_distance": 4,
            "failed_deviation": 0,
            "failed_box_size": 0,
            "failed_aspect_ratio": 0,
            "classifier_score": 0.35,
            "decision": False,
        },
        {
            "run_id": "test_clip",
            "batch_index": 2,
            "num_trackers": 5,
            "pairs_evaluated": 10,
            "failed_speed": 3,
            "failed_distance": 7,
            "failed_deviation": 0,
            "failed_box_size": 0,
            "failed_aspect_ratio": 0,
            "classifier_score": 0.49,
            "decision": False,
        },
    ]

    summary = summarize_run_trace(records)
    assert summary["total_batches"] == 2
    assert summary["max_trackers"] == 5
    assert summary["total_pairs_evaluated"] == 16
    assert summary["dominant_filter"] == "TOO_FAR"
    assert summary["max_classifier_score"] == 0.49
    assert summary["alert_count"] == 0
    assert summary["primary_cause"] == "CLASSIFIER_LOW_SCORE"
