import logging
import os
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np

from System.Functions.Detector.base import BaseDetector, DetectionBox
from System.Functions.Detector.motion import MotionFallbackDetector

logger = logging.getLogger("argus.detector.yolo")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# Standard COCO vehicle class mappings
COCO_VEHICLE_LABELS = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
# Torchvision 1-indexed COCO categories
TORCHVISION_VEHICLE_LABELS = {
    3: "car",
    4: "motorcycle",
    6: "bus",
    8: "truck",
}


class ModernYoloDetector(BaseDetector):
    """
    Modern Vehicle Detector (Permissive License: Apache-2.0 / BSD / MIT).
    Supports:
      1. OpenCV DNN ONNX Engine (YOLOX / YOLO ONNX models)
      2. Torchvision SSDLite320-MobileNetV3 (BSD-3-Clause)
    Filters detections strictly to vehicle categories (car, truck, bus, motorcycle)
    above a configurable confidence threshold.
    Falls back to MotionFallbackDetector if model weights are not installed.
    """

    def __init__(
        self,
        confidence_threshold: Optional[float] = None,
        target_size: Optional[tuple] = None,
        model_path: Optional[str] = None
    ):
        self.conf_threshold = confidence_threshold or float(os.getenv("ARGUS_DETECTOR_CONFIDENCE", "0.35"))
        self.target_size = target_size or (
            int(os.getenv("ARGUS_INFERENCE_WIDTH", "480")),
            int(os.getenv("ARGUS_INFERENCE_HEIGHT", "360"))
        )
        self.model_path = model_path
        self._motion_fallback = MotionFallbackDetector()
        self._backend = None
        self._net = None
        self._init_attempted = False

    @property
    def name(self) -> str:
        return "yolo"

    @property
    def is_low_quality(self) -> bool:
        return self._backend is None

    def _init_model(self):
        if self._init_attempted:
            return
        self._init_attempted = True

        # 1. Check for ONNX models in models/
        onnx_candidates = [
            MODELS_DIR / "yolox_s.onnx",
            MODELS_DIR / "yolov8n.onnx",
        ]
        if self.model_path:
            onnx_candidates.insert(0, Path(self.model_path))

        for p in onnx_candidates:
            if p.exists():
                try:
                    self._net = cv2.dnn.readNetFromONNX(str(p))
                    # Prefer multi-threaded CPU backend
                    self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                    self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                    self._backend = "onnx"
                    logger.info(f"Loaded modern ONNX vehicle detector from: {p.name}")
                    return
                except Exception as ex:
                    logger.warning(f"Failed to load ONNX model {p}: {ex}")

        # 2. Try Torchvision BSD-3 SSDLite detector
        try:
            import torch
            import torchvision
            from torchvision.models.detection import ssdlite320_mobilenet_v3_large

            weights_file = MODELS_DIR / "ssdlite320_mobilenet_v3_large.pth"
            if weights_file.exists():
                model = ssdlite320_mobilenet_v3_large()
                state_dict = torch.load(str(weights_file), map_location="cpu", weights_only=True)
                model.load_state_dict(state_dict)
                model.eval()
                self._net = model
                self._backend = "torchvision"
                logger.info("Loaded Torchvision SSDLite320 vehicle detector from local weights")
                return
        except Exception as e:
            logger.debug(f"Torchvision detector initialization skipped: {e}")

        logger.warning(
            "No trained model weights found in models/. "
            "Falling back to MotionFallbackDetector (low-quality detection mode). "
            "Run 'python scripts/download_models.py' to download verified weights."
        )

    def detect(self, frame: np.ndarray, **kwargs) -> List[DetectionBox]:
        self._init_model()

        if self._backend is None or frame is None or frame.size == 0:
            return self._motion_fallback.detect(frame, **kwargs)

        h, w = frame.shape[:2]

        if self._backend == "onnx":
            return self._detect_onnx(frame, w, h)
        elif self._backend == "torchvision":
            return self._detect_torchvision(frame, w, h)

        return self._motion_fallback.detect(frame, **kwargs)

    def _detect_onnx(self, frame: np.ndarray, orig_w: int, orig_h: int) -> List[DetectionBox]:
        try:
            blob = cv2.dnn.blobFromImage(
                frame,
                scalefactor=1.0 / 255.0,
                size=(640, 640),
                mean=[0, 0, 0],
                swapRB=True,
                crop=False
            )
            self._net.setInput(blob)
            outputs = self._net.forward()

            boxes: List[DetectionBox] = []

            # Handle YOLO output shape: [1, 84, 8400] or [1, 8400, 84]
            if len(outputs.shape) == 3:
                predictions = outputs[0]
                if predictions.shape[0] < predictions.shape[1]:
                    predictions = predictions.T

                x_scale = orig_w / 640.0
                y_scale = orig_h / 640.0

                for pred in predictions:
                    # pred: [cx, cy, bw, bh, class_0, class_1, ...]
                    scores = pred[4:]
                    class_id = int(np.argmax(scores))
                    score = float(scores[class_id])

                    if score >= self.conf_threshold and class_id in COCO_VEHICLE_LABELS:
                        cx, cy, bw, bh = pred[:4]
                        xmin = max(0.0, float((cx - bw / 2.0) * x_scale))
                        ymin = max(0.0, float((cy - bh / 2.0) * y_scale))
                        xmax = min(float(orig_w), float((cx + bw / 2.0) * x_scale))
                        ymax = min(float(orig_h), float((cy + bh / 2.0) * y_scale))

                        boxes.append([
                            COCO_VEHICLE_LABELS[class_id],
                            xmin, xmax, ymin, ymax,
                            round(score, 3)
                        ])

            return boxes[:12]
        except Exception as e:
            logger.error(f"Error during ONNX vehicle inference: {e}")
            return self._motion_fallback.detect(frame)

    def _detect_torchvision(self, frame: np.ndarray, orig_w: int, orig_h: int) -> List[DetectionBox]:
        try:
            import torch
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            tensor_frame = torch.from_numpy(rgb_frame).permute(2, 0, 1).float() / 255.0

            with torch.no_grad():
                predictions = self._net([tensor_frame])[0]

            boxes: List[DetectionBox] = []
            pred_boxes = predictions["boxes"].cpu().numpy()
            pred_scores = predictions["scores"].cpu().numpy()
            pred_labels = predictions["labels"].cpu().numpy()

            for box, score, label in zip(pred_boxes, pred_scores, pred_labels):
                if score >= self.conf_threshold and int(label) in TORCHVISION_VEHICLE_LABELS:
                    xmin, ymin, xmax, ymax = box
                    boxes.append([
                        TORCHVISION_VEHICLE_LABELS[int(label)],
                        float(xmin), float(xmax), float(ymin), float(ymax),
                        round(float(score), 3)
                    ])

            return boxes[:12]
        except Exception as e:
            logger.error(f"Error during Torchvision vehicle inference: {e}")
            return self._motion_fallback.detect(frame)
