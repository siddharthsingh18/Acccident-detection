from fastapi import APIRouter, Request
from ..models.schemas import HealthResponse
from ..services.health import get_system_health

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health", response_model=HealthResponse, summary="Check Argus microservices health")
async def health_check(request: Request):
    """Probe all Argus microservices (ports 10000, 10002, 10004, 10008), database, and ffmpeg."""
    return await get_system_health(request)
