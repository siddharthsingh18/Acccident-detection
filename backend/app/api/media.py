from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..services.media import get_thumbnail_file, sanitize_id

router = APIRouter(prefix="/media", tags=["media"])

@router.get("/thumbnails/{id}", summary="Serve incident thumbnail image with fallback")
async def get_thumbnail(id: str):
    """
    Serve incident thumbnail.
    Accepts '{id}' or '{id}.jpg'.
    Returns real JPEG if available, extracts from AVI clip if on disk, or serves UI/notfound.png fallback.
    """
    # Strip optional .jpg suffix if provided in URL
    raw_id = id[:-4] if id.lower().endswith(".jpg") else id
    try:
        safe_id = sanitize_id(raw_id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ID", "message": str(e)},
        )

    file_path = get_thumbnail_file(safe_id)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "THUMBNAIL_NOT_FOUND", "message": "Thumbnail and fallback image unavailable"},
        )

    media_type = "image/jpeg" if file_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )
