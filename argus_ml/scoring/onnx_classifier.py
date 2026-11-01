import json
import logging
import os
from pathlib import Path
import time
from typing import Optional, Dict, Any, List
import cv2
import numpy as np

from .base import CrashScorer, ClipInput, ScoreResult

logger = logging.getLogger("argus.ml.onnx_classifier")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class OnnxClassifierScorer:
    """
    Pluggable 2D/3D CNN ONNX Classifier Scorer (e.g., ResNet-50 crash classifier).
    Configurable via external ONNX file and sidecar JSON configuration.
    Reports unavailable when weights are not mounted.
    """
    def __init__(
        self,
        model_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
    ):
        self.name = "resnet_onnx"
        self.version = "0.1.0-draft"
        self.trained_on = "Awaiting ONNX weights export"
        self.calibration_date = None
        self.available = False
        self.reason_unavailable = "Model weights file not mounted in models/"
        self.session = None
        self.threshold = 0.50
        self.input_size = (224, 224)
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

        # Resolve model path
        env_path = os.environ.get("RESNET_ONNX_PATH")
        candidate = (
            Path(model_path) if model_path
            else (Path(env_path) if env_path
            else (PROJECT_ROOT / "models" / "resnet_onnx.onnx"))
        )

        if not candidate.exists():
            # Check secondary location in artifacts/models
            alt = PROJECT_ROOT / "artifacts" / "models" / "resnet_onnx.onnx"
            if alt.exists():
                candidate = alt

        if not candidate.exists():
            self.available = False
            self.reason_unavailable = f"Model weights file not mounted in {candidate.parent}"
            return

        # Attempt to load with onnxruntime
        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(str(candidate))
            self.input_name = self.session.get_inputs()[0].name
            self.available = True
            self.reason_unavailable = None
            logger.info(f"OnnxClassifierScorer loaded ONNX model from {candidate}")
        except Exception as e:
            self.available = False
            self.reason_unavailable = f"Failed to initialize ONNX runtime: {e}"
            return

        # Load sidecar JSON configuration if available
        sidecar = config_path or candidate.with_suffix(".json")
        if sidecar.exists():
            try:
                with open(sidecar, "r") as f:
                    cfg = json.load(f)
                self.input_size = tuple(cfg.get("input_size", [224, 224]))
                if "mean" in cfg:
                    self.mean = np.array(cfg["mean"], dtype=np.float32)
                if "std" in cfg:
                    self.std = np.array(cfg["std"], dtype=np.float32)
                self.threshold = float(cfg.get("threshold", 0.50))
                self.version = cfg.get("version", self.version)
                self.trained_on = cfg.get("trained_on", self.trained_on)
                self.calibration_date = cfg.get("calibration_date")
                logger.info(f"Loaded ONNX classifier sidecar configuration from {sidecar}")
            except Exception as e:
                logger.warning(f"Error parsing ONNX sidecar {sidecar}: {e}")

    def score(self, clip: ClipInput) -> ScoreResult:
        """
        Extract frame representations, run ONNX classification, and return crash probability.
        """
        if not self.available or self.session is None:
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=False,
                latency_ms=None,
                reason_unavailable=self.reason_unavailable or "OnnxClassifierScorer unavailable",
            )

        start_time = time.perf_counter()
        frames = clip.frames
        if not frames:
            latency = (time.perf_counter() - start_time) * 1000.0
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=bool(self.calibration_date),
                latency_ms=round(latency, 2),
                details={"reason": "No frames provided in clip"},
            )

        try:
            # Pick representative frame (middle of clip)
            mid_frame = frames[len(frames) // 2]
            img = cv2.resize(mid_frame, self.input_size)
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            elif img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Normalize with mean and std
            norm_img = (img.astype(np.float32) / 255.0 - self.mean) / self.std
            tensor = np.transpose(norm_img, (2, 0, 1))[np.newaxis, ...]  # (1, 3, H, W)

            outputs = self.session.run(None, {self.input_name: tensor})
            logits = outputs[0][0]

            # Binary or 2-class softmax
            if len(logits) == 1:
                prob = 1.0 / (1.0 + np.exp(-float(logits[0])))
            elif len(logits) >= 2:
                exp_logits = np.exp(logits - np.max(logits))
                probs = exp_logits / np.sum(exp_logits)
                prob = float(probs[1])
            else:
                prob = 0.0

            fired = bool(prob >= self.threshold)
            latency = (time.perf_counter() - start_time) * 1000.0

            return ScoreResult(
                score=round(float(prob), 4),
                fired=fired,
                calibrated=bool(self.calibration_date),
                latency_ms=round(latency, 2),
                details={"model": "resnet_onnx"},
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"ONNX classifier inference error: {e}")
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=False,
                latency_ms=round(latency, 2),
                reason_unavailable=f"Inference error: {e}",
            )
