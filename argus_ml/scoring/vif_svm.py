import logging
import os
from pathlib import Path
import pickle
import time
from typing import Optional
import cv2
import numpy as np

from VIF.vif import VIF
from .base import CrashScorer, ClipInput, ScoreResult

logger = logging.getLogger("argus.ml.vif_svm")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class VifSvmScorer:
    """
    Wraps the legacy Violent Flows (VIF) feature extractor and Support Vector Machine (SVM)
    classifier behind the unified CrashScorer interface.
    Supports both ONNX runtime and native scikit-learn models.
    """
    def __init__(
        self,
        model_path: Optional[Path] = None,
        use_onnx: bool = True,
        threshold: float = 0.50,
    ):
        self.name = "vif_svm"
        self.version = "1.0.0"
        self.trained_on = "Argus Surveillance Dataset (Alexandria & Regional Cameras)"
        self.calibration_date = "2021-03-01"
        self.threshold = threshold
        self.available = False
        self.reason_unavailable = None
        self.use_onnx = use_onnx

        # Initialize VIF feature extractor
        try:
            self.vif = VIF()
        except Exception as e:
            self.available = False
            self.reason_unavailable = f"Failed to initialize VIF module: {e}"
            return

        # Locate model weights
        onnx_candidate = model_path or (PROJECT_ROOT / "artifacts" / "models" / "vif_svm.onnx")
        sav_candidate = PROJECT_ROOT / "VIF" / "model-svm1.sav"

        self.ort_session = None
        self.clf = None

        if self.use_onnx and onnx_candidate.exists():
            try:
                import onnxruntime as ort
                self.ort_session = ort.InferenceSession(str(onnx_candidate))
                self.input_name = self.ort_session.get_inputs()[0].name
                self.available = True
                logger.info(f"VifSvmScorer loaded ONNX model from {onnx_candidate}")
                return
            except Exception as e:
                logger.warning(f"Failed to load ONNX model ({e}), falling back to scikit-learn pickle.")

        # Fallback to legacy scikit-learn pickle
        if sav_candidate.exists():
            try:
                with open(sav_candidate, "rb") as f:
                    self.clf = pickle.load(f)
                # Apply scikit-learn 1.x compatibility patch if needed
                if "probA_" in self.clf.__dict__ and not hasattr(self.clf, "_probA"):
                    self.clf._probA = self.clf.__dict__["probA_"]
                if "probB_" in self.clf.__dict__ and not hasattr(self.clf, "_probB"):
                    self.clf._probB = self.clf.__dict__["probB_"]
                self.available = True
                logger.info(f"VifSvmScorer loaded scikit-learn SVM from {sav_candidate}")
            except Exception as e:
                self.available = False
                self.reason_unavailable = f"Failed to load legacy SVM model: {e}"
        else:
            self.available = False
            self.reason_unavailable = f"No model file found at {sav_candidate} or {onnx_candidate}"

    def score(self, clip: ClipInput) -> ScoreResult:
        """
        Extract VIF features and predict crash probability.
        """
        if not self.available:
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=False,
                latency_ms=None,
                reason_unavailable=self.reason_unavailable or "VifSvmScorer unavailable",
            )

        start_time = time.perf_counter()

        frames = clip.frames
        if not frames or len(frames) < 15:
            latency = (time.perf_counter() - start_time) * 1000.0
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=True,
                latency_ms=round(latency, 2),
                details={"reason": "Insufficient frames for VIF analysis (minimum 15 required)"},
            )

        # Convert RGB/BGR frames to grayscale if necessary
        gray_frames = []
        for f in frames:
            if len(f.shape) == 3 and f.shape[2] == 3:
                gray_frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
            else:
                gray_frames.append(f)

        try:
            feature_vec = self.vif.process(gray_frames)
            features = feature_vec.reshape(1, 304).astype(np.float32)

            if self.ort_session is not None:
                ort_outs = self.ort_session.run(None, {self.input_name: features})
                raw_pred = ort_outs[0][0]
                proba_out = ort_outs[1][0]
                if isinstance(proba_out, dict):
                    crash_prob = float(proba_out.get(1, proba_out.get(1.0, 0.0)))
                else:
                    crash_prob = float(proba_out[1])
            else:
                raw_pred = self.clf.predict(features)[0]
                if hasattr(self.clf, "predict_proba"):
                    proba = self.clf.predict_proba(features)[0]
                    crash_prob = float(proba[1])
                else:
                    crash_prob = 1.0 if raw_pred == 1.0 else 0.0

            fired = bool(raw_pred == 1.0 or crash_prob >= self.threshold)
            latency = (time.perf_counter() - start_time) * 1000.0

            return ScoreResult(
                score=round(max(0.0, min(1.0, crash_prob)), 4),
                fired=fired,
                calibrated=True,
                latency_ms=round(latency, 2),
                details={"raw_prediction": float(raw_pred)},
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Error executing VIF scoring: {e}")
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=False,
                latency_ms=round(latency, 2),
                reason_unavailable=f"Inference error: {e}",
            )
