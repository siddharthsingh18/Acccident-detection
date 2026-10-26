import os
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse, FileResponse

from ..models.schemas import Incident, IncidentsListResponse
from ..services.database import (
    query_incidents,
    query_recent_incidents,
    query_incident_by_id,
)
from ..services.media import sanitize_id
from ..services.video import (
    get_or_create_incident_mp4,
    parse_range_header,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

@router.get("", response_model=IncidentsListResponse, summary="List & search road accident incidents")
async def list_incidents(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or DD/MM/YYYY)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD or DD/MM/YYYY)"),
    start_time: Optional[str] = Query(None, description="Start time (HH:MM or HH:MM:SS)"),
    end_time: Optional[str] = Query(None, description="End time (HH:MM or HH:MM:SS)"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    district: Optional[str] = Query(None, description="Filter by district designation"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    cursor: Optional[int] = Query(None, description="Pagination cursor (rowid < cursor)"),
):
    """
    Search and filter historical crash records from SQLite database with cursor pagination.
    Replaces RunGui.py search filter.
    """
    items, next_cursor, has_more = query_incidents(
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        city=city,
        district=district,
        limit=limit,
        cursor=cursor,
    )
    return IncidentsListResponse(
        items=items,
        count=len(items),
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get("/recent", response_model=List[Incident], summary="Retrieve 10 most recent incidents")
async def get_recent():
    """
    Returns the 10 newest detected road crashes.
    Direct replacement for RunGui.py 'Recent' button.
    """
    return query_recent_incidents(limit=10)

@router.get("/export", summary="Export incident search results as CSV")
@router.get("/export/csv", summary="Export incident search results as CSV")
async def export_incidents_csv(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or DD/MM/YYYY)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD or DD/MM/YYYY)"),
    start_time: Optional[str] = Query(None, description="Start time (HH:MM or HH:MM:SS)"),
    end_time: Optional[str] = Query(None, description="End time (HH:MM or HH:MM:SS)"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    district: Optional[str] = Query(None, description="Filter by district designation"),
):
    """Generate and download a CSV file of incidents matching the current search filters."""
    import csv
    import io

    items, _, _ = query_incidents(
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        city=city,
        district=district,
        limit=10000,
        cursor=None,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Incident ID",
        "Camera ID",
        "Starting Frame",
        "Crash Time",
        "City",
        "District",
        "Status",
        "Thumbnail URL",
        "Video URL"
    ])
    for item in items:
        writer.writerow([
            item.id,
            item.camera_id,
            item.starting_frame_id,
            item.crash_time,
            item.city or "Unknown",
            item.district or "Unknown",
            "Complete" if item.from_no == 5 else f"Chunk {item.from_no}",
            item.thumbnail_url,
            item.video_url
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=argus_incidents.csv"
        }
    )

@router.get("/{id}", response_model=Incident, summary="Get details for a specific incident")
async def get_incident(id: str):
    """
    Lookup an incident by canonical id (camera_id_frame_id, e.g. '1528_76') or database rowid.
    """
    try:
        safe_id = sanitize_id(id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ID", "message": str(e)},
        )

    incident = query_incident_by_id(safe_id)
    if not incident:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Incident '{safe_id}' not found"},
        )
    return incident

@router.get("/{id}/video", summary="Stream stitched incident video clip with HTTP Range seeking")
async def stream_incident_video(id: str, request: Request):
    """
    Stream stitched crash video.
    1. Retrieves existing H.264 MP4 from cache or transcodes from raw AVI with ffmpeg.
    2. Serves with HTTP 206 Partial Content (Range requests) to enable seek/scrubbing in HTML5 video players.
    """
    try:
        safe_id = sanitize_id(id)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ID", "message": str(e)},
        )

    try:
        mp4_path = await get_or_create_incident_mp4(safe_id)
    except FileNotFoundError as fnf:
        raise HTTPException(
            status_code=404,
            detail={"code": "VIDEO_NOT_FOUND", "message": str(fnf)},
        )
    except RuntimeError as re:
        raise HTTPException(
            status_code=500,
            detail={"code": "TRANSCODING_ERROR", "message": str(re)},
        )
    except Exception as ex:
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": str(ex)},
        )

    file_size = mp4_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        start, end = parse_range_header(range_header, file_size)
        content_length = (end - start) + 1

        def iterfile():
            with open(mp4_path, "rb") as f:
                f.seek(start)
                bytes_left = content_length
                chunk_size = 64 * 1024
                while bytes_left > 0:
                    read_len = min(chunk_size, bytes_left)
                    data = f.read(read_len)
                    if not data:
                        break
                    bytes_left -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)

    return FileResponse(
        mp4_path,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )
