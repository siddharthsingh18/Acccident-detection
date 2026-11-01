from enum import Enum
import logging
from typing import Dict, List, Optional, Tuple, Literal
from .base import CrashScorer, ClipInput, ScoreResult
from backend.app.models.schemas import ModelScores, ScorerResult, ScorerStatus, ModelsStatusResponse

logger = logging.getLogger("argus.ml.ensemble")


class EnsemblePolicy(str, Enum):
    ANY = "any"
    ALL = "all"
    MAJORITY = "majority"
    WEIGHTED = "weighted"


class CrashEnsemble:
    """
    Unified multi-model ensembling engine for road accident detection.
    Combines individual CrashScorer models under configurable voting policies.
    Gracefully handles degraded operational states when scorers are unavailable.
    """
    def __init__(
        self,
        scorers: Optional[List[CrashScorer]] = None,
        policy: str = "majority",
        threshold: float = 0.60,
        weights: Optional[Dict[str, float]] = None,
        min_available: int = 1,
    ):
        self.scorers: List[CrashScorer] = scorers or []
        self.policy = policy if policy in ("any", "all", "majority", "weighted") else "majority"
        self.threshold = threshold
        self.weights = weights or {"vif_svm": 1.0, "convae": 1.0, "resnet_onnx": 1.0}
        self.min_available = min_available

    def add_scorer(self, scorer: CrashScorer) -> None:
        """Register a new scorer into the ensemble."""
        self.scorers.append(scorer)

    def get_status(self) -> ModelsStatusResponse:
        """
        Produce real-time status summary across all registered models.
        """
        statuses: List[ScorerStatus] = []
        for s in self.scorers:
            statuses.append(
                ScorerStatus(
                    name=s.name,
                    available=s.available,
                    version=s.version,
                    trained_on=s.trained_on,
                    calibration_date=s.calibration_date,
                    reason_unavailable=s.reason_unavailable,
                )
            )

        available_count = sum(1 for s in self.scorers if s.available)
        is_degraded = available_count < len(self.scorers)

        return ModelsStatusResponse(
            policy=self.policy,
            scorers=statuses,
            degraded=is_degraded,
        )

    def evaluate(self, clip: ClipInput) -> Tuple[ModelScores, bool, bool]:
        """
        Execute all registered scorers against the clip, aggregate decisions per policy,
        and return (ModelScores, decision, is_degraded).
        """
        scorer_results: List[ScorerResult] = []
        available_results: List[ScorerResult] = []

        for scorer in self.scorers:
            if scorer.available:
                try:
                    res = scorer.score(clip)
                    sr = ScorerResult(
                        name=scorer.name,
                        score=res.score,
                        fired=res.fired,
                        calibrated=res.calibrated,
                        available=True,
                        latency_ms=res.latency_ms,
                        reason_unavailable=res.reason_unavailable,
                    )
                    scorer_results.append(sr)
                    available_results.append(sr)
                except Exception as e:
                    logger.error(f"Error evaluating scorer {scorer.name}: {e}")
                    sr = ScorerResult(
                        name=scorer.name,
                        score=0.0,
                        fired=False,
                        calibrated=False,
                        available=False,
                        latency_ms=None,
                        reason_unavailable=f"Runtime error: {e}",
                    )
                    scorer_results.append(sr)
            else:
                sr = ScorerResult(
                    name=scorer.name,
                    score=0.0,
                    fired=False,
                    calibrated=False,
                    available=False,
                    latency_ms=None,
                    reason_unavailable=scorer.reason_unavailable or "Scorer offline",
                )
                scorer_results.append(sr)

        # Check degraded status
        is_degraded = len(available_results) < len(self.scorers)

        # Compute ensemble decision
        if not available_results:
            decision = False
        elif len(available_results) < self.min_available:
            # Fewer than required minimum available -> fallback to legacy vif_svm if present
            legacy_res = next((r for r in available_results if r.name == "vif_svm"), None)
            decision = legacy_res.fired if legacy_res else False
        else:
            if self.policy == "any":
                decision = any(r.fired for r in available_results)
            elif self.policy == "all":
                decision = all(r.fired for r in available_results)
            elif self.policy == "majority":
                fired_count = sum(1 for r in available_results if r.fired)
                decision = fired_count > (len(available_results) / 2.0)
            elif self.policy == "weighted":
                total_weight = sum(self.weights.get(r.name, 1.0) for r in available_results)
                weighted_sum = sum(r.score * self.weights.get(r.name, 1.0) for r in available_results)
                agg_score = weighted_sum / max(1e-6, total_weight)
                decision = agg_score >= self.threshold
            else:
                decision = any(r.fired for r in available_results)

        scores_payload = ModelScores(
            policy=self.policy,
            threshold=self.threshold,
            decision=decision,
            scorers=scorer_results,
        )

        return scores_payload, decision, is_degraded
