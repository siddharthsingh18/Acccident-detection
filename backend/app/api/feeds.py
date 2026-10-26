import logging
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..models.schemas import FeedResponse, FeedCancelResponse, ErrorResponse
from ..services.feed_manager import feed_manager
from ..services.media import sanitize_id


logger = logging.getLogger("argus.api.feeds")
router = APIRouter(prefix="/api/feeds", tags=["Feeds"])

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
