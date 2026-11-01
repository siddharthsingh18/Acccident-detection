import logging
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..models.schemas import SampleItemResponse
from ..services.sample_catalog import (
    list_samples,
    resolve_sample_path,
    get_or_create_thumbnail,
)

logger = logging.getLogger("argus.api.samples")
router = APIRouter(prefix="/api/samples", tags=["Samples"])

@router.get("", response_model=List[SampleItemResponse], summary="List all discoverable test dataset videos")
async def get_samples():
    """
    Scans configured SAMPLE_DIRS for video files (.mp4, .avi, .mkv, .mov),
    extracts metadata via ffprobe, resolves expected ground-truth labels from
    videos/manifest.json and directory names, and returns catalog items with stable IDs.
    """
    return list_samples()

@router.get("/{sample_id:path}/thumbnail", summary="Get or extract sample video thumbnail")
async def get_sample_thumbnail(sample_id: str):
    """
    Returns a JPEG thumbnail of the requested sample video, cached on disk under artifacts/cache/thumbnails/.
    """
    try:
        video_path = resolve_sample_path(sample_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error resolving sample thumbnail path for {sample_id}: {e}")
        raise HTTPException(status_code=400, detail="Invalid sample path.")

    thumb_path = get_or_create_thumbnail(video_path, sample_id)
    if not thumb_path or not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available.")

    return FileResponse(thumb_path, media_type="image/jpeg")
