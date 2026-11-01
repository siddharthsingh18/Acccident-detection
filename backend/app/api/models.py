import logging
import os
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter

from ..config import settings, PROJECT_ROOT
from ..models.schemas import ModelsStatusResponse, ScorerStatus
from argus_ml.scoring.ensemble import CrashEnsemble
from argus_ml.scoring.vif_svm import VifSvmScorer
from argus_ml.scoring.convae import ConvAEScorer
from argus_ml.scoring.onnx_classifier import OnnxClassifierScorer

logger = logging.getLogger("argus.api.models")
router = APIRouter(prefix="/api/models", tags=["Models"])

_cached_status: Optional[ModelsStatusResponse] = None
_cached_time: float = 0.0
CACHE_TTL_SEC: float = 3.0


def reset_models_cache() -> None:
    """Clear cached model status (primarily for unit tests and configuration changes)."""
    global _cached_status, _cached_time
    _cached_status = None
    _cached_time = 0.0


@router.get("/status", response_model=ModelsStatusResponse, summary="Get crash scoring models and ensemble status")
async def get_models_status():
    """
    Returns the real-time operational status of all registered crash scoring models,
    including version, training provenance, calibration dates, and ensemble policy.
    Results are cached with a short TTL to prevent disk I/O contention on high-frequency polling.
    """
    global _cached_status, _cached_time
    now = time.time()
    if _cached_status is not None and (now - _cached_time) < CACHE_TTL_SEC:
        return _cached_status

    policy = os.environ.get("CRASH_POLICY", os.environ.get("ARGUS_ENSEMBLE_POLICY", settings.CRASH_POLICY))
    if policy not in ("any", "all", "majority", "weighted"):
        policy = "majority"

    # Instantiate scorers
    vif = VifSvmScorer()
    convae = ConvAEScorer()
    resnet = OnnxClassifierScorer()

    ensemble = CrashEnsemble(scorers=[vif, convae, resnet], policy=policy)
    status = ensemble.get_status()

    _cached_status = status
    _cached_time = now
    return status
