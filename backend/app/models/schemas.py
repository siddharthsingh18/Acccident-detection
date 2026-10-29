from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class ErrorResponse(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of error")
    details: Optional[Any] = Field(None, description="Additional context or validation errors")

class ServiceHealth(BaseModel):
    name: str
    host: str
    port: int
    reachable: bool
    latency_ms: Optional[float] = None
    note: Optional[str] = None

class HealthResponse(BaseModel):
    status: str = Field(..., description="'ok', 'degraded', or 'down'")
    services: Dict[str, ServiceHealth]
    database: Dict[str, Any]
    ffmpeg: Dict[str, Any]
    zmq_listener: Optional[Dict[str, Any]] = None

class Alert(BaseModel):
    incident_id: str = Field(..., description="Unique incident identifier, e.g. 1528_76")
    camera_id: int
    starting_frame_id: int
    date: str
    time: str
    city: Optional[str] = None
    district: Optional[str] = None
    thumbnail_url: str
    video_url: str

class Incident(BaseModel):
    id: str = Field(..., description="Canonical string ID, e.g. '1528_76' or rowid")
    rowid: int
    camera_id: int
    starting_frame_id: int
    city: Optional[str] = None
    district: Optional[str] = None
    crash_time: str
    from_no: Optional[int] = Field(None, description="Stitching chunk progress (5 = complete)")
    thumbnail_url: str
    video_url: str
    review_status: Optional[str] = Field(None, description="NULL, 'confirmed', or 'false_alarm'")
    review_note: Optional[str] = Field(None, description="Operator review comments (max 500 chars)")
    reviewed_at: Optional[str] = Field(None, description="ISO timestamp when review occurred")

class ReviewIncidentRequest(BaseModel):
    status: str = Field(..., description="'confirmed' or 'false_alarm'")
    note: Optional[str] = Field(None, max_length=500, description="Operator note (max 500 characters)")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("confirmed", "false_alarm"):
            raise ValueError("status must be 'confirmed' or 'false_alarm'")
        return v

class IncidentsListResponse(BaseModel):
    items: List[Incident]
    count: int
    next_cursor: Optional[int] = Field(None, description="rowid cursor for the next page")
    has_more: bool

class FeedProgress(BaseModel):
    frames_sent: int = 0
    total_frames: int = 0
    percent: float = 0.0

class FeedResponse(BaseModel):
    id: str
    camera_id: int
    city: str
    district: str
    status: str = Field(..., description="queued, processing, done, failed, cancelled, low-quality detection mode")
    detection_mode: Optional[str] = Field("standard", description="standard, yolo, or low-quality detection mode")
    progress: FeedProgress
    thumbnail_url: str
    error: Optional[str] = None
    created_at: str

class FeedCancelResponse(BaseModel):
    id: str
    status: str
    message: str
