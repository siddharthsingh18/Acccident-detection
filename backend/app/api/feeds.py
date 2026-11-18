import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import settings, PROJECT_ROOT
from ..models.schemas import (
    FeedResponse,
    FeedCancelResponse,
    ErrorResponse,
    StartFeedFromSampleRequest,
    RerunFeedRequest,
    UploadCleanupResponse,
    RunComparisonResponse,
)
from ..services.feed_manager import feed_manager
from ..services.media import sanitize_id
from ..services.sample_catalog import resolve_sample_path


logger = logging.getLogger("argus.api.feeds")
router = APIRouter(prefix="/api/feeds", tags=["Feeds"])

def get_sample_video_path(safe_name: str) -> Optional[Path]:
    """Resolve sample video path across videos/, videos/Extra/, or Joiner/vids/."""
    for folder in [PROJECT_ROOT / "videos", PROJECT_ROOT / "videos" / "Extra", PROJECT_ROOT / "Joiner" / "vids"]:
        candidate = folder / safe_name
        if candidate.exists():
            return candidate
    return None

@router.get("/samples", summary="List built-in dataset surveillance video feeds")
async def get_sample_feeds():
    """Returns curated sample videos from the Argus dataset for quick 1-click testing."""
    return [
        # --- ACCIDENT FEEDS (VERIFIED CRASHES) ---
        {
            "id": "1528",
            "filename": "1528.mp4",
            "camera_id": 1528,
            "city": "Shibin El Kom",
            "district": "District 13",
            "label": "Camera 1528 (Shibin El Kom - High-Speed Junction Impact)",
            "description": "High-velocity road intersection collision with vehicle deflection",
            "has_accident": True,
            "incident_id": "1528_76",
            "video_url": "/api/feeds/sample/1528.mp4",
            "output_video_url": "/api/incidents/1528_76/video"
        },
        {
            "id": "1506",
            "filename": "1506.mp4",
            "camera_id": 1506,
            "city": "Asyut",
            "district": "District 16",
            "label": "Camera 1506 (Asyut Junction - Van Collision)",
            "description": "Intersection collision at frame 106 between white van and passenger vehicle",
            "has_accident": True,
            "incident_id": "1506_106",
            "video_url": "/api/feeds/sample/1506.mp4",
            "output_video_url": "/api/incidents/1506_106/video"
        },
        {
            "id": "1513",
            "filename": "1513.mp4",
            "camera_id": 1513,
            "city": "Aswan",
            "district": "District 21",
            "label": "Camera 1513 (Aswan Highway - Side Collision)",
            "description": "Highway collision at frame 61 with traffic deceleration",
            "has_accident": True,
            "incident_id": "1513_61",
            "video_url": "/api/feeds/sample/1513.mp4",
            "output_video_url": "/api/incidents/1513_61/video"
        },
        {
            "id": "1543",
            "filename": "1543.mp4",
            "camera_id": 1543,
            "city": "Asyut",
            "district": "District 10",
            "label": "Camera 1543 (Asyut Avenue - Crash)",
            "description": "Multi-lane urban crash with tracked vehicle trajectory",
            "has_accident": True,
            "incident_id": "1543_166",
            "video_url": "/api/feeds/sample/1543.mp4",
            "output_video_url": "/api/incidents/1543_166/video"
        },
        {
            "id": "1508",
            "filename": "1508.mp4",
            "camera_id": 1508,
            "city": "Fayyum",
            "district": "District 26",
            "label": "Camera 1508 (Fayyum Expressway - Impact)",
            "description": "High-velocity roadway collision with lateral deceleration",
            "has_accident": True,
            "incident_id": "1508_31",
            "video_url": "/api/feeds/sample/1508.mp4",
            "output_video_url": "/api/incidents/1508_31/video"
        },
        {
            "id": "1516",
            "filename": "1516.mp4",
            "camera_id": 1516,
            "city": "Shubra El-Kheima",
            "district": "District 27",
            "label": "Camera 1516 (Shubra Corridor - Junction Crash)",
            "description": "Busy corridor crash with multi-vehicle tracking bounds",
            "has_accident": True,
            "incident_id": "1516_61",
            "video_url": "/api/feeds/sample/1516.mp4",
            "output_video_url": "/api/incidents/1516_61/video"
        },
        {
            "id": "1518",
            "filename": "1518.mp4",
            "camera_id": 1518,
            "city": "Shubra El-Kheima",
            "district": "District 25",
            "label": "Camera 1518 (Shubra Boulevard - Side Impact)",
            "description": "Boulevard side-swipe crash with Horn-Schunck violent flow spikes",
            "has_accident": True,
            "incident_id": "1518_1",
            "video_url": "/api/feeds/sample/1518.mp4",
            "output_video_url": "/api/incidents/1518_1/video"
        },
        {
            "id": "1519",
            "filename": "1519.mp4",
            "camera_id": 1519,
            "city": "Qalyub",
            "district": "District 22",
            "label": "Camera 1519 (Qalyub Highway Entry - Collision)",
            "description": "Highway ramp vehicle merging impact at frame 16",
            "has_accident": True,
            "incident_id": "1519_16",
            "video_url": "/api/feeds/sample/1519.mp4",
            "output_video_url": "/api/incidents/1519_16/video"
        },
        {
            "id": "1521",
            "filename": "1521.mp4",
            "camera_id": 1521,
            "city": "Qena",
            "district": "District 2",
            "label": "Camera 1521 (Qena Avenue - Crossroad Impact)",
            "description": "Avenue crossroad crash with sharp velocity reduction",
            "has_accident": True,
            "incident_id": "1521_121",
            "video_url": "/api/feeds/sample/1521.mp4",
            "output_video_url": "/api/incidents/1521_121/video"
        },
        {
            "id": "1522",
            "filename": "1522.mp4",
            "camera_id": 1522,
            "city": "Marsa Matruh",
            "district": "District 6",
            "label": "Camera 1522 (Marsa Matruh Road - Lateral Crash)",
            "description": "Coastal roadway collision with abrupt orientation change",
            "has_accident": True,
            "incident_id": "1522_61",
            "video_url": "/api/feeds/sample/1522.mp4",
            "output_video_url": "/api/incidents/1522_61/video"
        },
        {
            "id": "1529",
            "filename": "1529.mp4",
            "camera_id": 1529,
            "city": "Bilbais",
            "district": "District 29",
            "label": "Camera 1529 (Bilbais Arterial - Multi-Vehicle)",
            "description": "Arterial road collision involving commercial transport vehicles",
            "has_accident": True,
            "incident_id": "1529_181",
            "video_url": "/api/feeds/sample/1529.mp4",
            "output_video_url": "/api/incidents/1529_181/video"
        },
        {
            "id": "1533",
            "filename": "1533.mp4",
            "camera_id": 1533,
            "city": "Cairo",
            "district": "District 18",
            "label": "Camera 1533 (Cairo Boulevard - T-Bone Collision)",
            "description": "Metropolitan intersection vehicle impact at frame 91",
            "has_accident": True,
            "incident_id": "1533_91",
            "video_url": "/api/feeds/sample/1533.mp4",
            "output_video_url": "/api/incidents/1533_91/video"
        },
        {
            "id": "1534",
            "filename": "1534.mp4",
            "camera_id": 1534,
            "city": "Ismailia",
            "district": "District 27",
            "label": "Camera 1534 (Ismailia Junction - Vehicle Crash)",
            "description": "Urban intersection vehicle impact with trajectory deviation",
            "has_accident": True,
            "incident_id": "1534_91",
            "video_url": "/api/feeds/sample/1534.mp4",
            "output_video_url": "/api/incidents/1534_91/video"
        },
        {
            "id": "1548",
            "filename": "1548.mp4",
            "camera_id": 1548,
            "city": "Luxor",
            "district": "District 14",
            "label": "Camera 1548 (Luxor Avenue - Night Collision)",
            "description": "Nighttime road collision with sharp optical flow spike at frame 226",
            "has_accident": True,
            "incident_id": "1548_226",
            "video_url": "/api/feeds/sample/1548.mp4",
            "output_video_url": "/api/incidents/1548_226/video"
        },
        {
            "id": "1566",
            "filename": "1566.mp4",
            "camera_id": 1566,
            "city": "Hurghada",
            "district": "District 16",
            "label": "Camera 1566 (Hurghada Coastal - Road Impact)",
            "description": "Coastal highway collision at frame 136 with sudden stop",
            "has_accident": True,
            "incident_id": "1566_136",
            "video_url": "/api/feeds/sample/1566.mp4",
            "output_video_url": "/api/incidents/1566_136/video"
        },

        # --- NORMAL TRAFFIC FEEDS (SAFE ROADS - ZERO ACCIDENTS) ---
        {
            "id": "1600",
            "filename": "1600.mp4",
            "camera_id": 1600,
            "city": "Cairo",
            "district": "District 5",
            "label": "Camera 1600 (Bridge Expressway - Full Steady Traffic)",
            "description": "Continuous multi-vehicle highway flow with zero collisions or trajectory anomalies",
            "has_accident": False,
            "incident_id": None,
            "video_url": "/api/feeds/sample/1600.mp4",
            "output_video_url": None
        },
        {
            "id": "1601",
            "filename": "1601.mp4",
            "camera_id": 1601,
            "city": "Cairo",
            "district": "District 5",
            "label": "Camera 1601 (Bridge Expressway - Morning Commute)",
            "description": "Smooth highway commuter stream with stable speeds and zero incidents",
            "has_accident": False,
            "incident_id": None,
            "video_url": "/api/feeds/sample/1601.mp4",
            "output_video_url": None
        },
        {
            "id": "1602",
            "filename": "1602.mp4",
            "camera_id": 1602,
            "city": "Cairo",
            "district": "District 5",
            "label": "Camera 1602 (Bridge Expressway - Commercial Transit)",
            "description": "Steady commercial transit flow with full adherence to lane boundaries",
            "has_accident": False,
            "incident_id": None,
            "video_url": "/api/feeds/sample/1602.mp4",
            "output_video_url": None
        },
        {
            "id": "1701",
            "filename": "1701.mp4",
            "camera_id": 1701,
            "city": "Giza",
            "district": "District 3",
            "label": "Camera 1701 (Downtown Signal Junction - Urban Queue)",
            "description": "Traffic light intersection with orderly queues and smooth signal departures",
            "has_accident": False,
            "incident_id": None,
            "video_url": "/api/feeds/sample/1701.mp4",
            "output_video_url": None
        }
    ]

@router.api_route("/sample/{filename}", methods=["GET", "HEAD"], summary="Stream sample dataset video")
async def stream_sample_video(filename: str):
    safe_name = Path(filename).name
    video_path = get_sample_video_path(safe_name)
    if not video_path:
        raise HTTPException(status_code=404, detail=f"Sample video '{safe_name}' not found.")
    return FileResponse(video_path, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})

@router.post("/sample", response_model=FeedResponse, status_code=201)
async def start_sample_feed(
    sample_id: str = Form(..., description="Sample video ID (e.g. 1528)"),
    city: str = Form("Cairo"),
    district: str = Form("District 1")
):
    safe_name = f"{Path(sample_id).stem}.mp4"
    video_path = get_sample_video_path(safe_name)
    if not video_path:
        raise HTTPException(status_code=404, detail=f"Sample video '{safe_name}' not found.")
    
    try:
        cam_id = int(Path(sample_id).stem)
    except ValueError:
        cam_id = 9999

    return await feed_manager.start_feed(
        file_path=video_path,
        camera_id=cam_id,
        city=city,
        district=district,
        is_test=True
    )

@router.post(
    "/from-sample",
    response_model=FeedResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Validation or format error"},
        404: {"model": ErrorResponse, "description": "Sample video not found"},
        409: {"model": ErrorResponse, "description": "Another feed is actively processing"}
    },
    summary="Start processing a test feed directly from the sample catalog without copying"
)
async def create_feed_from_sample(payload: StartFeedFromSampleRequest):
    """
    Launch feed processing using an existing sample catalog video in-place without disk copying.
    Enforces path traversal safety and single-active-feed constraint.
    """
    video_path = resolve_sample_path(payload.sample_id)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample video '{payload.sample_id}' not found.")

    # Validate video container
    feed_manager.validate_video_file(video_path)

    # Derive camera ID if not explicitly provided
    if payload.camera_id is not None:
        cam_id = payload.camera_id
    elif video_path.stem.isdigit():
        try:
            cam_id = int(video_path.stem)
        except ValueError:
            cam_id = 9999
    else:
        cam_id = 9999

    city = payload.city or "Cairo"
    district = payload.district or "District 1"

    return await feed_manager.start_feed(
        file_path=video_path,
        camera_id=cam_id,
        city=city,
        district=district,
        is_test=payload.is_test
    )

@router.post(
    "",
    response_model=FeedResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Validation or format error"},
        409: {"model": ErrorResponse, "description": "Another feed is actively processing"},
        413: {"model": ErrorResponse, "description": "File size exceeds limit"}
    }
)
async def create_feed(
    file: UploadFile = File(..., description="Video file (mp4, avi, mkv, mov)"),
    camera_id: int = Form(..., description="Camera identifier"),
    city: str = Form("Cairo", description="City location"),
    district: str = Form("District 1", description="District location"),
    detector_confidence: Optional[float] = Form(None, description="Detector confidence override (0.05 - 0.95)"),
    adaptive_box_filter: Optional[bool] = Form(None, description="Adaptive box filter toggle"),
    distance_factor: Optional[float] = Form(None, description="Distance factor multiplier (0.10 - 1.00)"),
    single_vehicle_mode: Optional[bool] = Form(None, description="Single vehicle mode toggle"),
    frame_stride: Optional[int] = Form(None, description="Frame stride override (1 - 10)"),
    is_test: bool = Form(False, description="Tag run as test"),
):
    """
    Upload and start processing a CCTV camera video feed.
    Inspects real content with ffprobe, generates thumbnail with play overlay,
    and streams 30-frame batches with 15-frame overlap via a headless CameraNode subprocess.
    """
    if detector_confidence is not None and not (0.05 <= detector_confidence <= 0.95):
        raise HTTPException(status_code=422, detail="detector_confidence must be between 0.05 and 0.95")
    if distance_factor is not None and not (0.10 <= distance_factor <= 1.00):
        raise HTTPException(status_code=422, detail="distance_factor must be between 0.10 and 1.00")
    if frame_stride is not None and not (1 <= frame_stride <= 10):
        raise HTTPException(status_code=422, detail="frame_stride must be between 1 and 10")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    run_id = str(uuid.uuid4())
    upload_dir = settings.UPLOADS_DIR / run_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"original{ext}"

    # Stream file to disk while enforcing max file size
    total_size = 0
    try:
        with open(upload_path, "wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > settings.MAX_UPLOAD_SIZE_BYTES:
                    shutil.rmtree(upload_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB"
                    )
                out_f.write(chunk)
    except HTTPException:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    # Write upload metadata for retention and replay
    try:
        meta_file = upload_dir / "metadata.json"
        with open(meta_file, "w", encoding="utf-8") as meta_f:
            json.dump({
                "run_id": run_id,
                "original_filename": file.filename,
                "file_size": total_size,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "camera_id": camera_id,
                "city": city,
                "district": district,
            }, meta_f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to record upload metadata for {run_id}: {e}")

    # Real content validation with ffprobe
    try:
        feed_manager.validate_video_file(upload_path)
    except HTTPException:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Video inspection error: {str(e)}")

    # Start feed process with matching feed_id and run_id and per-run overrides
    overrides = {
        "detector_confidence": detector_confidence,
        "adaptive_box_filter": adaptive_box_filter,
        "distance_factor": distance_factor,
        "single_vehicle_mode": single_vehicle_mode,
        "frame_stride": frame_stride,
    }
    return await feed_manager.start_feed(
        file_path=upload_path,
        camera_id=camera_id,
        city=city,
        district=district,
        is_test=is_test,
        feed_id=run_id,
        overrides=overrides,
    )

@router.get(
    "/{id}/thumbnail",
    responses={
        200: {"content": {"image/jpeg": {}}, "description": "Video first-frame thumbnail with play overlay"},
        404: {"model": ErrorResponse, "description": "Feed or thumbnail not found"}
    }
)
async def get_feed_thumbnail(id: str):
    """Serve the first-frame thumbnail with play-button overlay."""
    safe_id = sanitize_id(id)
    thumb_path = feed_manager.get_thumbnail_path(safe_id)
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available.")
    return FileResponse(thumb_path, media_type="image/jpeg")

@router.get(
    "/{id}",
    response_model=FeedResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Feed not found"}
    }
)
async def get_feed_status(id: str):
    """Retrieve status and frame progress for a feed."""
    safe_id = sanitize_id(id)
    return feed_manager.get_feed(safe_id)

@router.post(
    "/{id}/cancel",
    response_model=FeedCancelResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Feed not found"}
    }
)
async def cancel_feed(id: str):
    """Cancel an active camera feed subprocess."""
    safe_id = sanitize_id(id)
    return await feed_manager.cancel_feed(safe_id)


@router.post(
    "/{id}/rerun",
    response_model=FeedResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse, "description": "Feed or video file not found"},
        409: {"model": ErrorResponse, "description": "Another feed is actively processing"}
    },
    summary="Replay or re-run a previous feed or upload with current or overridden configuration"
)
async def rerun_feed(id: str, payload: Optional[RerunFeedRequest] = None):
    """
    Replay an existing video upload or sample run directly from disk without re-uploading bytes.
    Enforces retention policy check and allows config overrides.
    """
    safe_id = sanitize_id(id)
    video_path = feed_manager.get_feed_video_path(safe_id)
    if not video_path or not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Video media for feed '{safe_id}' not found on disk. Uploaded file may have expired."
        )

    prev_item = feed_manager.feeds.get(safe_id)
    cam_id = payload.camera_id if (payload and payload.camera_id is not None) else (prev_item.camera_id if prev_item else 9999)
    city = (payload.city if payload and payload.city else None) or (prev_item.city if prev_item else "Cairo")
    district = (payload.district if payload and payload.district else None) or (prev_item.district if prev_item else "District 1")
    is_test = payload.is_test if (payload and payload.is_test is not None) else (prev_item.is_test if prev_item else False)
    detector = payload.detector if payload else None

    # Merge overrides from payload or prior run
    prev_cfg = (prev_item.detector_config if prev_item else {}) or {}
    overrides = {
        "detector_confidence": payload.detector_confidence if payload and payload.detector_confidence is not None else prev_cfg.get("detector_confidence"),
        "adaptive_box_filter": payload.adaptive_box_filter if payload and payload.adaptive_box_filter is not None else prev_cfg.get("adaptive_box_filter"),
        "distance_factor": payload.distance_factor if payload and payload.distance_factor is not None else prev_cfg.get("distance_factor"),
        "single_vehicle_mode": payload.single_vehicle_mode if payload and payload.single_vehicle_mode is not None else prev_cfg.get("single_vehicle_mode"),
        "frame_stride": payload.frame_stride if payload and payload.frame_stride is not None else prev_cfg.get("frame_stride"),
    }

    if overrides["detector_confidence"] is not None and not (0.05 <= overrides["detector_confidence"] <= 0.95):
        raise HTTPException(status_code=422, detail="detector_confidence must be between 0.05 and 0.95")
    if overrides["distance_factor"] is not None and not (0.10 <= overrides["distance_factor"] <= 1.00):
        raise HTTPException(status_code=422, detail="distance_factor must be between 0.10 and 1.00")
    if overrides["frame_stride"] is not None and not (1 <= overrides["frame_stride"] <= 10):
        raise HTTPException(status_code=422, detail="frame_stride must be between 1 and 10")

    return await feed_manager.start_feed(
        file_path=video_path,
        camera_id=cam_id,
        city=city,
        district=district,
        is_test=is_test,
        detector_override=detector,
        overrides=overrides,
    )


@router.get(
    "/{id}/compare/{other_id}",
    summary="Side-by-side comparison of two feed runs (detector, vehicles seen, alerts, trace summary)"
)
async def compare_feed_runs(id: str, other_id: str):
    """Retrieve side-by-side comparison of two runs."""
    safe_a = sanitize_id(id)
    safe_b = sanitize_id(other_id)

    feed_a = feed_manager.feeds.get(safe_a)
    feed_b = feed_manager.feeds.get(safe_b)

    resp_a = feed_a.to_response().model_dump() if feed_a else {"id": safe_a, "status": "unknown"}
    resp_b = feed_b.to_response().model_dump() if feed_b else {"id": safe_b, "status": "unknown"}

    cfg_a = resp_a.get("detector_config", {})
    cfg_b = resp_b.get("detector_config", {})

    config_diff = {}
    all_keys = set(cfg_a.keys()).union(set(cfg_b.keys()))
    for k in all_keys:
        if cfg_a.get(k) != cfg_b.get(k):
            config_diff[k] = {"run_a": cfg_a.get(k), "run_b": cfg_b.get(k)}

    # Read traces if available
    from argus_ml.trace import read_run_trace, summarize_run_trace
    trace_a = summarize_run_trace(read_run_trace(safe_a))
    trace_b = summarize_run_trace(read_run_trace(safe_b))

    return {
        "run_a_id": safe_a,
        "run_b_id": safe_b,
        "run_a": {
            **resp_a,
            "trace_summary": trace_a,
        },
        "run_b": {
            **resp_b,
            "trace_summary": trace_b,
        },
        "differences": {
            "detector_changed": resp_a.get("detector_name") != resp_b.get("detector_name"),
            "vehicles_diff": (resp_b.get("vehicles_detected_count", 0) - resp_a.get("vehicles_detected_count", 0)),
            "alerts_diff": (resp_b.get("anomalies_detected", 0) - resp_a.get("anomalies_detected", 0)),
            "config_diff": config_diff,
        }
    }



@router.post(
    "/uploads/cleanup",
    response_model=UploadCleanupResponse,
    summary="Enforce upload retention policy and clean up expired upload directories"
)
async def cleanup_uploads(retention_days: int = 7, max_disk_mb: Optional[int] = None):
    """
    Remove upload directories older than retention_days or prune oldest if max_disk_mb is exceeded.
    """
    max_bytes = max_disk_mb * 1024 * 1024 if max_disk_mb is not None else None
    stats = feed_manager.cleanup_uploads(retention_days=retention_days, max_disk_bytes=max_bytes)
    return UploadCleanupResponse(**stats)


@router.get("/trace/{run_id}", summary="Get pipeline trace diagnostics for a camera or feed run")
async def get_run_trace(run_id: str):
    """Retrieve diagnostic pipeline telemetry explaining why an alert did or did not fire."""
    from argus_ml.trace import read_run_trace, summarize_run_trace
    records = read_run_trace(run_id)
    raw_feed = feed_manager.feeds.get(run_id)
    feed_item = raw_feed.to_response() if raw_feed else None
    quality = feed_item.detection_quality if feed_item else None
    detector_name = feed_item.detector_name if feed_item else None

    if not records:
        if feed_item:
            fallback_cause = "LOW_QUALITY_DETECTION" if quality in ("motion_fallback", "unavailable") else "NO_TRACE"
            frames_sent = feed_item.progress.frames_sent if feed_item.progress else 0
            batches_cnt = feed_item.batches_processed or (max(1, frames_sent // 30) if frames_sent > 0 else 0)
            return {
                "run_id": run_id,
                "has_trace": True,
                "summary": {
                    "total_batches": batches_cnt,
                    "batches_processed": batches_cnt,
                    "max_trackers": feed_item.vehicles_detected_count,
                    "total_pairs_evaluated": 0,
                    "filter_counts": {},
                    "dominant_filter": "NONE",
                    "max_classifier_score": 0.0,
                    "alert_count": len(feed_item.detected_incidents),
                    "detector_used": detector_name or "unknown",
                    "detection_quality": quality or "unknown",
                    "primary_cause": fallback_cause,
                },
                "records_count": 0,
            }
        return {"run_id": run_id, "has_trace": False, "summary": None, "message": "No trace recorded"}

    summary = summarize_run_trace(records, detection_quality=quality)
    if detector_name and not summary.get("detector_used"):
        summary["detector_used"] = detector_name
    if quality and not summary.get("detection_quality"):
        summary["detection_quality"] = quality
    return {"run_id": run_id, "has_trace": True, "summary": summary, "records_count": len(records)}


@router.get("/config/active", summary="Get active CV pipeline detector and geometry flags")
async def get_active_config():
    """Retrieve active CV configuration for reproducible runs."""
    return {
        "detector": os.getenv("ARGUS_DETECTOR", os.getenv("DETECTOR", "legacy")).lower(),
        "trace_enabled": os.getenv("ARGUS_TRACE", "false").lower() in ("true", "1", "yes"),
        "adaptive_box_filter": os.getenv("CRASH_ADAPTIVE_BOX_FILTER", "false").lower() in ("true", "1", "yes"),
        "distance_factor": float(os.getenv("CRASH_DISTANCE_FACTOR", "0.25")),
        "single_vehicle": os.getenv("CRASH_SINGLE_VEHICLE", "false").lower() in ("true", "1", "yes"),
        "classifier_threshold": float(os.getenv("CRASH_CLASSIFIER_THRESHOLD", "0.50")),
        "ensemble_enabled": os.getenv("ARGUS_ENABLE_ENSEMBLE", "false").lower() in ("true", "1", "yes"),
        "crash_policy": os.getenv("CRASH_POLICY", "majority")
    }
