import logging
from typing import List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..models.schemas import SampleItemResponse
from ..services.sample_catalog import (
    list_samples,
    resolve_sample_path,
    get_or_create_thumbnail,
    get_or_create_sample_mp4,
)
from ..services.video import stream_video_response

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

@router.api_route("/{sample_id:path}/video", methods=["GET", "HEAD"], summary="Stream sample dataset video")
async def stream_sample_video(sample_id: str, request: Request):
    """
    Stream sample video transcoded to web-compatible H.264 MP4 with HTTP Range request support.
    """
    try:
        mp4_path = await get_or_create_sample_mp4(sample_id)
    except HTTPException:
        raise
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail={"code": "VIDEO_NOT_FOUND", "message": str(fnf)})
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ID", "message": str(ve)})
    except Exception as ex:
        logger.error(f"Failed to transcode/stream sample video '{sample_id}': {ex}")
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(ex)})

    return stream_video_response(mp4_path, request)


