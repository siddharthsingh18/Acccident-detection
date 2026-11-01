import json
import logging
import os
from pathlib import Path
import time
from typing import Optional, Dict, Any
import cv2
import numpy as np

from .base import CrashScorer, ClipInput, ScoreResult

logger = logging.getLogger("argus.ml.convae")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class ConvAEScorer:
    """
    Spatio-Temporal Convolutional AutoEncoder (ConvAE/ConvLSTM) anomaly crash scorer.
    Computes frame reconstruction error over temporal sliding windows.
    Requires an authentic state_dict checkpoint and calibration file.
    """
    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        calibration_path: Optional[Path] = None,
        allow_dev: Optional[bool] = None,
    ):
        self.name = "convae"
        self.version = "0.2.0-dota"
        self.trained_on = "DoTA Benchmark (Detection of Traffic Anomaly)"
        self.calibration_date = None
        self.available = False
        self.calibrated = False
        self.reason_unavailable = None
        self.model = None
        self.threshold = 0.50
        self.calibration_data: Dict[str, Any] = {}

        if allow_dev is None:
            allow_dev = os.environ.get("ARGUS_ALLOW_DEV_CHECKPOINT", "false").lower() in ("true", "1", "yes")
        self.allow_dev = allow_dev

        # Verify PyTorch availability
        try:
            import torch
            import torch.nn as nn
            self.torch = torch
            self.nn = nn
        except ImportError as e:
            self.available = False
            self.reason_unavailable = f"PyTorch is not installed: {e}"
            return

        # Resolve checkpoint path
        ckpt_dir = Path(os.environ.get("CONVAE_CHECKPOINT_DIR", str(PROJECT_ROOT / "artifacts" / "checkpoints" / "convae")))
        custom_ckpt = os.environ.get("CONVAE_CHECKPOINT_PATH")
        best_ckpt = Path(custom_ckpt) if custom_ckpt else (ckpt_dir / "best_model.pth")
        smoke_ckpt = ckpt_dir / "smoke_checkpoint.pth"

        resolved_ckpt = None
        if checkpoint_path and Path(checkpoint_path).exists():
            resolved_ckpt = Path(checkpoint_path)
            if "smoke" in resolved_ckpt.name.lower() or "dev" in resolved_ckpt.name.lower():
                self.trained_on = "DEV SMOKE TEST (not for real use)"
                logger.warning("ConvAEScorer running with DEV SMOKE TEST checkpoint!")
        elif best_ckpt.exists():
            resolved_ckpt = best_ckpt
        elif self.allow_dev and smoke_ckpt.exists():
            resolved_ckpt = smoke_ckpt
            self.trained_on = "DEV SMOKE TEST (not for real use)"
            logger.warning("ConvAEScorer running with DEV SMOKE TEST checkpoint!")

        if not resolved_ckpt or not resolved_ckpt.exists():
            self.available = False
            self.reason_unavailable = f"Trained weights checkpoint not found in {ckpt_dir}"
            return

        # Attempt safe state_dict load
        try:
            from types import SimpleNamespace
            from ConvAE import ConvLSTMED
            device = "cpu"
            if self.torch.backends.mps.is_available():
                device = "mps"
            elif self.torch.cuda.is_available():
                device = "cuda"
            self.device = device

            # Ground rule: torch.load with weights_only=True
            state = self.torch.load(resolved_ckpt, map_location=device, weights_only=True)
            state_dict = state.get("state_dict", state) if isinstance(state, dict) else state

            model_args = SimpleNamespace(mode="gray")
            self.model = ConvLSTMED(model_args)
            self.model.load_state_dict(state_dict)
            self.model.to(device)
            self.model.eval()
            self.available = True
            logger.info(f"ConvAEScorer loaded checkpoint from {resolved_ckpt} on {device}")
        except Exception as e:
            self.available = False
            self.reason_unavailable = f"Failed to load checkpoint: {e}"
            return

        # Check calibration sidecar
        calib_file = calibration_path or (PROJECT_ROOT / "artifacts" / "calibration" / "convae_calibration.json")
        if calib_file.exists():
            try:
                with open(calib_file, "r") as f:
                    self.calibration_data = json.load(f)
                self.calibrated = True
                self.calibration_date = self.calibration_data.get("calibration_date")
                self.threshold = float(self.calibration_data.get("threshold", 0.50))
                logger.info(f"ConvAEScorer loaded calibration from {calib_file}")
            except Exception as e:
                logger.warning(f"Failed to load calibration file {calib_file}: {e}")
                self.calibrated = False
        else:
            self.calibrated = False
            self.calibration_date = None

    def score(self, clip: ClipInput) -> ScoreResult:
        """
        Evaluate temporal frames through ConvAE and compute reconstruction anomaly error.
        """
        if not self.available or self.model is None:
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=False,
                latency_ms=None,
                reason_unavailable=self.reason_unavailable or "ConvAEScorer unavailable",
            )

        start_time = time.perf_counter()
        frames = clip.frames
        if not frames or len(frames) < 10:
            latency = (time.perf_counter() - start_time) * 1000.0
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=self.calibrated,
                latency_ms=round(latency, 2),
                details={"reason": "Insufficient frames for ConvAE sequence (minimum 10 required)"},
            )

        try:
            # Resize and normalize frames to (1, SeqLen, Height, Width) for gray ConvLSTMED
            resized = []
            for f in frames[:30]:  # Cap at 30 frames per standard window
                img = cv2.resize(f, (227, 227))
                if len(img.shape) == 3 and img.shape[2] == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                resized.append(img.astype(np.float32) / 255.0)

            # Tensor shape: (1, T, 227, 227)
            arr = np.array(resized)  # (T, 227, 227)
            tensor = self.torch.tensor(arr, dtype=self.torch.float32).unsqueeze(0).to(self.device)

            with self.torch.no_grad():
                recon = self.model(tensor)
                # Compute MSE reconstruction error
                mse = float(self.torch.mean((tensor - recon) ** 2).item())

            # Calibrate score to [0.0, 1.0]
            if self.calibrated and self.calibration_data:
                min_err = float(self.calibration_data.get("min_error", 0.01))
                max_err = float(self.calibration_data.get("max_error", 0.15))
                norm_score = (mse - min_err) / max(1e-6, (max_err - min_err))
                score = float(np.clip(norm_score, 0.0, 1.0))
            else:
                # Raw uncalibrated heuristic scaling
                score = float(np.clip(mse / 0.10, 0.0, 1.0))

            fired = bool(score >= self.threshold)
            latency = (time.perf_counter() - start_time) * 1000.0

            return ScoreResult(
                score=round(score, 4),
                fired=fired,
                calibrated=self.calibrated,
                latency_ms=round(latency, 2),
                details={"reconstruction_mse": round(mse, 6)},
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"ConvAE inference error: {e}")
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=self.calibrated,
                latency_ms=round(latency, 2),
                reason_unavailable=f"Inference error: {e}",
            )
