from abc import ABC, abstractmethod
from typing import List, Tuple, Any, Optional
import numpy as np

# Standard detection box format: [class_name, xmin, xmax, ymin, ymax, score]
DetectionBox = List[Any]

# Recognized vehicle categories in COCO datasets
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "motorbike", "vehicle"}


class BaseDetector(ABC):
    """
    Abstract base detector interface.
    Every detector accepts a single RGB/BGR frame and returns a list of vehicle detection boxes.
    """

    @abstractmethod
    def detect(self, frame: np.ndarray, **kwargs) -> List[DetectionBox]:
        """
        Detect vehicles in the provided image frame.
        :param frame: H x W x 3 image array (BGR or RGB)
        :param kwargs: Optional parameters such as frame_index or video_name
        :return: List of [class_name, xmin, xmax, ymin, ymax, score]
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the detector."""
        pass

    @property
    def is_low_quality(self) -> bool:
        """Indicates whether this detector is a low-quality motion fallback."""
        return False
