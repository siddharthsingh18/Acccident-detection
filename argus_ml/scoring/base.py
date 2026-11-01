from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
import numpy as np


@dataclass
class ClipInput:
    """
    Standard input representation for crash scoring models.
    Frames are expected as BGR or grayscale numpy arrays (default target: 480x360).
    """
    frames: List[np.ndarray]
    track_trajectories: Optional[List[Any]] = None
    fps: float = 30.0
    camera_id: Optional[int] = None
    start_frame_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreResult:
    """
    Unified result produced by any CrashScorer implementation.
    """
    score: float  # Range: [0.0, 1.0]
    fired: bool
    calibrated: bool = False
    latency_ms: Optional[float] = None
    reason_unavailable: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class CrashScorer(Protocol):
    """
    Unified Protocol interface for all road crash and anomaly scorers in Argus.
    """
    name: str
    available: bool
    reason_unavailable: Optional[str]
    version: str
    trained_on: str
    calibration_date: Optional[str]

    def score(self, clip: ClipInput) -> ScoreResult:
        """
        Evaluate a sequence of frames and return an atomic crash score result.
        """
        ...
