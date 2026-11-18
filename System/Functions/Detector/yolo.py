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

# Strict COCO vehicle class mappings
# Standard COCO 0-indexed categories (e.g. YOLOX ONNX)
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
    Permissive Neural Vehicle Detector (BSD-3-Clause / Apache-2.0).
    Supported backends:
      1. Torchvision SSDLite320-MobileNetV3 (BSD-3-Clause)
      2. OpenCV DNN ONNX Engine (e.g. YOLOX-Small, Apache-2.0)
    Filters detections strictly to vehicle categories (car, motorcycle, bus, truck).
    Configurable confidence threshold (ARGUS_DETECTOR_CONFIDENCE, default 0.35).
    Configurable frame stride (ARGUS_DETECTOR_STRIDE, default 1) with temporal box persistence.
    Falls back gracefully to MotionFallbackDetector when model weights are not installed.
    """

    def __init__(
        self,
        confidence_threshold: Optional[float] = None,
        target_size: Optional[tuple] = None,
        model_path: Optional[str] = None,
        frame_stride: Optional[int] = None,
    ):
        self.conf_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else float(os.getenv("ARGUS_DETECTOR_CONFIDENCE", "0.35"))
        )
        self.frame_stride = max(
            1,
            frame_stride
            if frame_stride is not None
            else int(os.getenv("ARGUS_DETECTOR_STRIDE", "1"))
        )
        self.target_size = target_size or (
            int(os.getenv("ARGUS_INFERENCE_WIDTH", "480")),
            int(os.getenv("ARGUS_INFERENCE_HEIGHT", "360")),
        )
        self.model_path = model_path
        self._motion_fallback = MotionFallbackDetector()
        self._backend: Optional[str] = None
        self._net = None
        self._init_attempted = False
        self._call_count = 0
        self._last_boxes: List[DetectionBox] = []

    @property
    def name(self) -> str:
        return "yolo"

    @property
    def backend(self) -> Optional[str]:
        self._init_model()
        return self._backend

    @property
    def is_available(self) -> bool:
        self._init_model()
        return self._backend is not None

    @property
    def is_low_quality(self) -> bool:
        self._init_model()
        return self._backend is None

    def _init_model(self):
        if self._init_attempted:
            return
        self._init_attempted = True

        # 1. Custom model path or permissive YOLOX ONNX (Apache-2.0)
        onnx_candidates = []
        if self.model_path:
            onnx_candidates.append(Path(self.model_path))
        onnx_candidates.append(MODELS_DIR / "yolox_s.onnx")

        for p in onnx_candidates:
            if p.exists() and p.suffix.lower() == ".onnx":
                try:
                    self._net = cv2.dnn.readNetFromONNX(str(p))
                    self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                    self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                    self._backend = "onnx"
                    logger.info(f"Loaded permissive ONNX vehicle detector from: {p.name}")
                    return
                except Exception as ex:
                    logger.warning(f"Failed to load ONNX model {p}: {ex}")

        # 2. Torchvision BSD-3 SSDLite detector
        try:
            import torch
            import torchvision
            from torchvision.models.detection import ssdlite320_mobilenet_v3_large

            weights_file = MODELS_DIR / "ssdlite320_mobilenet_v3_large.pth"
            if weights_file.exists():
                # weights_backbone=None sets reduced_tail=True, matching the COCO SSDLite weights architecture exactly
                model = ssdlite320_mobilenet_v3_large(weights_backbone=None)
                state_dict = torch.load(str(weights_file), map_location="cpu", weights_only=True)
                model.load_state_dict(state_dict)
                model.eval()
                self._net = model
                self._backend = "torchvision"
                logger.info("Loaded Torchvision SSDLite320 vehicle detector from local weights")
                return
            else:
                try:
                    from torchvision.models.detection import SSDLite320_MobileNet_V3_Large_Weights
                    model = ssdlite320_mobilenet_v3_large(weights=SSDLite320_MobileNet_V3_Large_Weights.DEFAULT)
                    model.eval()
                    self._net = model
                    self._backend = "torchvision"
                    logger.info("Loaded Torchvision SSDLite320 vehicle detector from torchvision cache")
                    return
                except Exception as ex:
                    logger.debug(f"Torchvision default weights loading skipped: {ex}")
        except Exception as e:
            logger.debug(f"Torchvision detector initialization skipped: {e}")

        logger.warning(
            "No permissive model weights found in models/. "
            "Falling back to MotionFallbackDetector (low-quality detection mode). "
            "Run 'python scripts/download_models.py --model ssdlite320-mobilenet' to download verified weights."
        )

    def detect(self, frame: np.ndarray, **kwargs) -> List[DetectionBox]:
        self._init_model()

        if self._backend is None or frame is None or frame.size == 0:
            return self._motion_fallback.detect(frame, **kwargs)

        # Frame stride logic: if stride > 1 and this frame is skipped, return persisted boxes
        frame_index = kwargs.get("frame_index")
        if frame_index is not None:
            skip = (self.frame_stride > 1 and (frame_index % self.frame_stride != 0))
        else:
            skip = (self.frame_stride > 1 and (self._call_count % self.frame_stride != 0))
        self._call_count += 1

        if skip and self._last_boxes:
            return [list(b) for b in self._last_boxes]

        h, w = frame.shape[:2]

        if self._backend == "onnx":
            boxes = self._detect_onnx(frame, w, h)
        elif self._backend == "torchvision":
            boxes = self._detect_torchvision(frame, w, h)
        else:
            boxes = self._motion_fallback.detect(frame, **kwargs)

        self._last_boxes = boxes
        return boxes

    def _detect_onnx(self, frame: np.ndarray, orig_w: int, orig_h: int) -> List[DetectionBox]:
        try:
            blob = cv2.dnn.blobFromImage(
                frame,
                scalefactor=1.0 / 255.0,
                size=(640, 640),
                mean=[0, 0, 0],
                swapRB=True,
                crop=False,
            )
            self._net.setInput(blob)
            outputs = self._net.forward()

            boxes: List[DetectionBox] = []

            # Handle YOLOX output shape: [1, 8400, 85]
            if len(outputs.shape) == 3:
                predictions = outputs[0]
                if predictions.shape[0] < predictions.shape[1]:
                    predictions = predictions.T

                x_scale = orig_w / 640.0
                y_scale = orig_h / 640.0

                for pred in predictions:
                    if len(pred) >= 85:
                        obj_conf = float(pred[4])
                        cls_scores = pred[5:]
                        class_id = int(np.argmax(cls_scores))
                        score = obj_conf * float(cls_scores[class_id])
                    else:
                        cls_scores = pred[4:]
                        class_id = int(np.argmax(cls_scores))
                        score = float(cls_scores[class_id])

                    if score >= self.conf_threshold and class_id in COCO_VEHICLE_LABELS:
                        cx, cy, bw, bh = pred[:4]
                        xmin = max(0.0, float((cx - bw / 2.0) * x_scale))
                        ymin = max(0.0, float((cy - bh / 2.0) * y_scale))
                        xmax = min(float(orig_w), float((cx + bw / 2.0) * x_scale))
                        ymax = min(float(orig_h), float((cy + bh / 2.0) * y_scale))

                        if xmax > xmin and ymax > ymin:
                            boxes.append([
                                COCO_VEHICLE_LABELS[class_id],
                                xmin, xmax, ymin, ymax,
                                round(score, 3),
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
                label_id = int(label)
                conf = float(score)
                # Strict vehicle class filter: car, motorcycle, bus, truck only
                if conf >= self.conf_threshold and label_id in TORCHVISION_VEHICLE_LABELS:
                    xmin, ymin, xmax, ymax = box
                    if xmax > xmin and ymax > ymin:
                        boxes.append([
                            TORCHVISION_VEHICLE_LABELS[label_id],
                            max(0.0, float(xmin)),
                            min(float(orig_w), float(xmax)),
                            max(0.0, float(ymin)),
                            min(float(orig_h), float(ymax)),
                            round(conf, 3),
                        ])

            return boxes[:12]
        except Exception as e:
            logger.error(f"Error during Torchvision vehicle inference: {e}")
            return self._motion_fallback.detect(frame)
