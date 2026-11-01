from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator

class ScorerResult(BaseModel):
    name: str = Field(..., description="Scorer identifier, e.g. vif_svm, convae, resnet_onnx")
    score: float = Field(..., ge=0.0, le=1.0, description="Model score between 0.0 and 1.0")
    fired: bool = Field(..., description="Whether model threshold was exceeded")
    calibrated: bool = Field(default=False, description="Whether score is calibrated probability")
    available: bool = Field(default=True, description="Whether scorer was active during inference")
    latency_ms: Optional[float] = Field(None, description="Inference latency in milliseconds")
    reason_unavailable: Optional[str] = Field(None, description="Explanation when scorer is unavailable")

class ModelScores(BaseModel):
    policy: Literal["any", "all", "majority", "weighted"] = Field(
        default="majority", description="Ensemble combination policy"
    )
    threshold: float = Field(default=0.60, ge=0.0, le=1.0, description="Decision threshold")
    decision: bool = Field(..., description="Ensemble crash verdict")
    scorers: List[ScorerResult] = Field(default_factory=list, description="List of individual scorer outcomes")

class ScorerStatus(BaseModel):
    name: str
    available: bool
    version: str
    trained_on: str
    calibration_date: Optional[str] = None
    reason_unavailable: Optional[str] = None

class ModelsStatusResponse(BaseModel):
    policy: Literal["any", "all", "majority", "weighted"] = "majority"
    scorers: List[ScorerStatus]
    degraded: bool = False

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
    model_scores: Optional[ModelScores] = Field(None, description="Ensemble and model score breakdown, or null")

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
    model_scores: Optional[ModelScores] = Field(None, description="Ensemble and model score breakdown, or null for legacy incidents")

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
    degraded: bool = Field(default=False, description="Whether feed is running in degraded mode with fewer scorers")
    active_scorers: List[str] = Field(default_factory=lambda: ["vif_svm"], description="List of active scorers for feed")
    progress: FeedProgress
    thumbnail_url: str
    error: Optional[str] = None
    created_at: str

class FeedCancelResponse(BaseModel):
    id: str
    status: str
    message: str

class SystemSettings(BaseModel):
    alert_sound_enabled: bool = Field(default=False, description="Whether incident audio alarm is enabled")
    siren_volume: int = Field(default=80, ge=0, le=100, description="Control room siren volume (0-100)")
    clip_retention_days: int = Field(default=30, ge=1, le=365, description="Video clip retention period in days (1-365)")
    min_alert_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum incident confidence threshold (0.0-1.0)")
    updated_at: Optional[str] = Field(None, description="ISO timestamp of last settings update")
    confidence_note: str = Field(
        default="Stored in system profile; not yet applied to legacy pipeline",
        description="Explains confidence filter applicability"
    )

class UpdateSettingsRequest(BaseModel):
    alert_sound_enabled: bool = Field(..., description="Whether incident audio alarm is enabled")
    siren_volume: int = Field(..., ge=0, le=100, description="Control room siren volume (0-100)")
    clip_retention_days: int = Field(..., ge=1, le=365, description="Video clip retention period in days (1-365)")
    min_alert_confidence: float = Field(..., ge=0.0, le=1.0, description="Minimum incident confidence threshold (0.0-1.0)")

class SampleItemResponse(BaseModel):
    id: str = Field(..., description="Stable URL-safe sample ID derived from relative path")
    name: str = Field(..., description="Sample filename, e.g. 1528.mp4")
    relative_path: str = Field(..., description="Relative path within project root, e.g. videos/1528.mp4")
    size_bytes: int = Field(..., description="File size in bytes")
    duration_s: Optional[float] = Field(None, description="Video duration in seconds")
    resolution: Optional[str] = Field(None, description="Video resolution, e.g. 640x360")
    fps: Optional[float] = Field(None, description="Frames per second")
    thumbnail_url: str = Field(..., description="URL endpoint to fetch sample video thumbnail")
    video_url: str = Field(..., description="URL endpoint to stream sample video")
    expected_label: Literal["accident", "normal", "unknown"] = Field(
        ..., description="Expected crash label derived from manifest or directory"
    )
    camera_id: Optional[int] = Field(None, description="Suggested camera identifier if known")
    city: Optional[str] = Field(None, description="Suggested city name if known")
    district: Optional[str] = Field(None, description="Suggested district if known")
    notes: Optional[str] = Field(None, description="Optional annotations or notes from manifest")

class StartFeedFromSampleRequest(BaseModel):
    sample_id: str = Field(..., description="Stable ID or relative path of the sample video")
    camera_id: Optional[int] = Field(None, description="Optional override camera ID")
    city: Optional[str] = Field(None, description="Optional override city")
    district: Optional[str] = Field(None, description="Optional override district")
