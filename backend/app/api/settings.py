from fastapi import APIRouter
from ..models.schemas import SystemSettings, UpdateSettingsRequest
from ..services.database import get_system_settings, update_system_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("", response_model=SystemSettings, summary="Get control room system settings")
async def get_settings():
    """
    Retrieve system configuration including audio siren status, volume (0-100),
    clip retention threshold (1-365 days), and collision detection confidence threshold.
    """
    return get_system_settings()

@router.put("", response_model=SystemSettings, summary="Update control room system settings")
async def update_settings(payload: UpdateSettingsRequest):
    """
    Update system configuration with validation:
    - alert_sound_enabled: bool
    - siren_volume: 0-100
    - clip_retention_days: 1-365
    - min_alert_confidence: 0.0-1.0
    """
    return update_system_settings(payload)
