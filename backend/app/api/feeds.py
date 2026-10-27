import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import settings, PROJECT_ROOT
from ..models.schemas import FeedResponse, FeedCancelResponse, ErrorResponse
from ..services.feed_manager import feed_manager
from ..services.media import sanitize_id


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
        district=district
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
    district: str = Form("District 1", description="District location")
):
    """
    Upload and start processing a CCTV camera video feed.
    Inspects real content with ffprobe, generates thumbnail with play overlay,
    and streams 30-frame batches with 15-frame overlap via a headless CameraNode subprocess.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    temp_id = str(uuid.uuid4())
    upload_path = settings.UPLOADS_DIR / f"{temp_id}_{file.filename}"

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
                    upload_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB"
                    )
                out_f.write(chunk)
    except HTTPException:
        upload_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    # Real content validation with ffprobe
    try:
        feed_manager.validate_video_file(upload_path)
    except HTTPException:
        upload_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Video inspection error: {str(e)}")

    # Start feed process
    return await feed_manager.start_feed(
        file_path=upload_path,
        camera_id=camera_id,
        city=city,
        district=district
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
