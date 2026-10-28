import os
from pathlib import Path
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # ZeroMQ nodes configuration
    ZMQ_HOST: str = "127.0.0.1"
    ZMQ_MASTER_HOST: str = Field(default_factory=lambda: os.getenv("ARGUS_MASTER_HOST", "127.0.0.1"))
    ZMQ_MASTER_PORT: int = 10000
    ZMQ_DETECT_PORT: int = 10002
    ZMQ_TRACK_PORT: int = 10004
    ZMQ_CRASH_PORT: int = 10008
    ZMQ_ALERT_PORT: int = 10010

    # Paths (can be relative to backend/ or project root)
    DATABASE_PATH: Path = Field(default_factory=lambda: PROJECT_ROOT / "System" / "Database" / "Argus_DB.db")
    SAVED_CRASH_VID_DIR: Path = Field(default_factory=lambda: PROJECT_ROOT / "saved_crash_vid")
    SAVED_FRAMES_VID_DIR: Path = Field(default_factory=lambda: PROJECT_ROOT / "saved_frames_vid")
    FALLBACK_IMAGE_PATH: Path = Field(default_factory=lambda: PROJECT_ROOT / "UI" / "notfound.png")
    PLAY_BUTTON_PATH: Path = Field(default_factory=lambda: PROJECT_ROOT / "UI" / "Play-Button-PNG-Picture.png")
    MEDIA_DIR: Path = Field(default_factory=lambda: BACKEND_DIR / "media")
    THUMBNAILS_DIR: Path = Field(default_factory=lambda: BACKEND_DIR / "media" / "thumbnails")
    VIDEO_CACHE_DIR: Path = Field(default_factory=lambda: BACKEND_DIR / "media" / "videos")
    UPLOADS_DIR: Path = Field(default_factory=lambda: BACKEND_DIR / "uploads")
    FEEDS_DIR: Path = Field(default_factory=lambda: BACKEND_DIR / "media" / "feeds")

    # Feed settings
    MAX_UPLOAD_SIZE_BYTES: int = 200 * 1024 * 1024  # 200 MB
    ALLOWED_EXTENSIONS: List[str] = [".mp4", ".avi", ".mkv", ".mov"]
    FEED_RETENTION_HOURS: int = 24

    @field_validator("DATABASE_PATH", "SAVED_CRASH_VID_DIR", "SAVED_FRAMES_VID_DIR", "FALLBACK_IMAGE_PATH", "PLAY_BUTTON_PATH", "MEDIA_DIR", "THUMBNAILS_DIR", "VIDEO_CACHE_DIR", "UPLOADS_DIR", "FEEDS_DIR", mode="before")
    @classmethod
    def resolve_paths(cls, v: Union[str, Path]) -> Path:
        if isinstance(v, str):
            p = Path(v)
            if not p.is_absolute():
                # Try relative to backend dir first, then project root
                if (BACKEND_DIR / p).exists() or not (PROJECT_ROOT / p).exists():
                    return (BACKEND_DIR / p).resolve()
                return (PROJECT_ROOT / p).resolve()
            return p.resolve()
        return v.resolve() if isinstance(v, Path) else Path(v)

    def init_directories(self) -> None:
        """Create media and cache directories if they don't exist."""
        self.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        self.THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
        self.VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.FEEDS_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.init_directories()
