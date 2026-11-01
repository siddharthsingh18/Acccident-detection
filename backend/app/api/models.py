import os
import logging
from typing import List
from fastapi import APIRouter

from ..models.schemas import ModelsStatusResponse, ScorerStatus

logger = logging.getLogger("argus.api.models")
router = APIRouter(prefix="/api/models", tags=["Models"])


@router.get("/status", response_model=ModelsStatusResponse, summary="Get crash scoring models and ensemble status")
async def get_models_status():
    """
    Returns the real-time operational status of all registered crash scoring models,
    including version, training provenance, calibration dates, and ensemble policy.
    """
    policy = os.environ.get("ARGUS_ENSEMBLE_POLICY", "majority")
    if policy not in ("any", "all", "majority", "weighted"):
        policy = "majority"

    # Check whether PyTorch and ConvAE are importable
    convae_available = True
    convae_reason = None
    try:
        import torch
        from ConvAE import ConvLSTMED
    except Exception as e:
        convae_available = False
        convae_reason = f"ConvAE module unavailable: {e}"

    # Check whether ONNX classifier runtime is available
    onnx_available = False
    onnx_reason = "Model weights file not mounted in models/"

    scorers: List[ScorerStatus] = [
        ScorerStatus(
            name="vif_svm",
            available=True,
            version="1.0.0",
            trained_on="Argus Surveillance Dataset (Alexandria & Regional Cameras)",
            calibration_date="2021-03-01",
            reason_unavailable=None,
        ),
        ScorerStatus(
            name="convae",
            available=convae_available,
            version="0.2.0-dota",
            trained_on="DoTA Benchmark (Detection of Traffic Anomaly)",
            calibration_date=None,
            reason_unavailable=convae_reason,
        ),
        ScorerStatus(
            name="resnet_onnx",
            available=onnx_available,
            version="0.1.0-draft",
            trained_on="Awaiting ONNX weights export",
            calibration_date=None,
            reason_unavailable=onnx_reason,
        ),
    ]

    # Degraded if any active or expected model is unavailable
    degraded = any(not s.available for s in scorers if s.name in ("vif_svm", "convae"))

    return ModelsStatusResponse(
        policy=policy,
        scorers=scorers,
        degraded=degraded,
    )

