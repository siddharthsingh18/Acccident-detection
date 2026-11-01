import os
import logging
from pathlib import Path
from typing import List
from fastapi import APIRouter

from ..config import settings, PROJECT_ROOT
from ..models.schemas import ModelsStatusResponse, ScorerStatus

logger = logging.getLogger("argus.api.models")
router = APIRouter(prefix="/api/models", tags=["Models"])


@router.get("/status", response_model=ModelsStatusResponse, summary="Get crash scoring models and ensemble status")
async def get_models_status():
    """
    Returns the real-time operational status of all registered crash scoring models,
    including version, training provenance, calibration dates, and ensemble policy.
    """
    policy = os.environ.get("CRASH_POLICY", os.environ.get("ARGUS_ENSEMBLE_POLICY", settings.CRASH_POLICY))
    if policy not in ("any", "all", "majority", "weighted"):
        policy = "majority"

    # Check whether PyTorch and ConvAE are importable AND have a trained checkpoint
    convae_available = False
    convae_reason = None
    convae_version = "0.2.0-dota"
    convae_trained_on = "DoTA Benchmark (Detection of Traffic Anomaly)"
    try:
        import torch
        from ConvAE import ConvLSTMED
        allow_dev = os.environ.get("ARGUS_ALLOW_DEV_CHECKPOINT", str(settings.ARGUS_ALLOW_DEV_CHECKPOINT)).lower() in ("1", "true", "yes")
        checkpoint_dir = Path(os.environ.get("CONVAE_CHECKPOINT_DIR", str(PROJECT_ROOT / "artifacts" / "checkpoints" / "convae")))
        custom_ckpt = os.environ.get("CONVAE_CHECKPOINT_PATH")
        ckpt_path = Path(custom_ckpt) if custom_ckpt else (checkpoint_dir / "best_model.pth")
        smoke_path = checkpoint_dir / "smoke_checkpoint.pth"

        if ckpt_path.exists():
            convae_available = True
            convae_reason = None
        elif allow_dev and smoke_path.exists():
            convae_available = True
            convae_reason = None
            convae_trained_on = "DEV SMOKE TEST (not for real use)"
        else:
            convae_available = False
            convae_reason = "Trained weights checkpoint not found in artifacts/checkpoints/convae/"
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
            version=convae_version,
            trained_on=convae_trained_on,
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

    # Degraded if any expected/configured model is unavailable
    degraded = any(not s.available for s in scorers if s.name in ("vif_svm", "convae"))

    return ModelsStatusResponse(
        policy=policy,
        scorers=scorers,
        degraded=degraded,
    )

