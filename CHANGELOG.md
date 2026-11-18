# Changelog

All notable changes to the Argus road-accident detection platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.3.0] - 2026-11-18

### Added
- **Permissive Neural Detector for Video Uploads (`System/Functions/Detector/`)**:
  - Automatic selection of permissive neural vehicle detector (`ModernYoloDetector`, Torchvision SSDLite320 MobileNetV3 / YOLOX ONNX) for uploaded and unannotated surveillance clips.
  - Strict vehicle class filtering (`{car, motorcycle, bus, truck}`) with configurable confidence threshold (`ARGUS_DETECTOR_CONFIDENCE`, default 0.35) and frame stride (`ARGUS_DETECTOR_STRIDE`, default 1).
  - SHA-256 verified download tool `scripts/download_models.py` with automatic integrity check and license display.
- **Detection Quality Taxonomy & Operator Warning System (`frontend/`, `backend/`)**:
  - Explicit quality states (`reference`, `neural`, `motion_fallback`, `unavailable`, `unknown`) persisted in SQLite and returned on all feed APIs.
  - Amber badge and warning banners preventing degraded runs from ever displaying as clean "Normal" or "0 anomalies".
  - Dedicated "No vehicles were detected in this video" outcome state when zero vehicles are found across the entire clip.
  - Pre-run upload warning modal alerting the operator if an upload will run without a neural detector.
- **Content-Addressed Box Registry & Persistent Storage**:
  - Replaced user-typed `camera_id` box file lookups with SHA-256 video content-hash matching (`boxes/registry.py`), eliminating cross-video annotation collisions.
  - Persistent upload storage under `backend/uploads/<run_id>/` with configurable retention cleanup (`POST /api/feeds/uploads/cleanup`).
  - Re-run upload endpoint (`POST /api/feeds/{id}/rerun`) enabling rapid testing of different detector and geometry settings without re-uploading.
- **Single-Vehicle Crash Geometry (`System/Functions/Crashing.py`)**:
  - Added opt-in single-vehicle collision detection (`CRASH_SINGLE_VEHICLE=true`, `CRASH_SINGLE_DECEL_THRESHOLD=0.60`, `CRASH_SINGLE_HEADING_ANGLE=45.0`) targeting guardrail impacts, barrier strikes, and spinouts with 0.0 false alarms/hr.
  - Enforced default-OFF isolation for `CRASH_ADAPTIVE_BOX_FILTER` and `CRASH_DISTANCE_FACTOR` after sweep analysis proved they increased distant false alarms.
- **Honest Held-Out CCTV Evaluation Suite (`docs/evaluation/`)**:
  - Unbundled CCTV surveillance evaluation set (`data/evaluation_manifest.csv`) strictly excluding the 19 bundled demo clips, with zero camera/video group overlap.
  - Systematic validation sweep (`docs/evaluation/validation_sweep.csv`) across 37 validation clips.
  - Single frozen evaluation on 33 held-out test clips (`docs/evaluation/heldout_test_metrics.csv` and `docs/evaluation/report.md`), proving false alarm rate drop from 530.2/hr down to 0.0/hr.
- **UI Run Summary Line & Trace Diagnostics**:
  - Real-time run summary line displaying detector used, detection quality, vehicles seen, batches processed, and alert count in both single-feed and batch views.
  - Trace drawer enriched with `Cause: LOW_QUALITY_DETECTION` and an amber degradation warning notice.
  - Troubleshooting guide in `README.md` with a 3-step diagnostic procedure.

---

## [2.2.0] - 2026-11-04

### Added
- **Pipeline Diagnostic Telemetry & Trace System (`argus_ml.trace`)**:
  - Structured per-batch JSONL execution tracer (`ARGUS_TRACE=true`) recording tracker counts, pair evaluations, filter drop breakdown (speed, distance, box size), ViF SVM decision scores, and primary drop causes without saving video frames.
  - Endpoints `GET /api/feeds/trace/{run_id}` and `GET /api/feeds/config/active` for runtime introspection.
- **Ground Truth Label Verification (`videos/manifest.json`)**:
  - Audited all 68 video sample clips via 12-frame contact sheets, classifying labels as `verified_by_frames`, `folder`, or `unknown`.
  - Reclassified `1507.mp4` (verified single-vehicle rollover) and excluded ambiguous near-miss `1559.mp4` from scoring (`unknown`).
  - Added zero-leakage camera group split validation test in `test_samples_catalog.py`.
- **Permissive Neural Detector Architecture & Licensing (`System/Functions/Detector/`)**:
  - `ModernYoloDetector` and factory with fallback to legacy/motion differencing when weights are unavailable.
  - Comprehensive licensing analysis (`docs/licensing.md`) documenting copyleft AGPL-3.0 vs. permissive alternatives (Apache-2.0 YOLOX, BSD-3 torchvision Faster R-CNN).
- **Configurable Crash Geometry Flags (`System/Functions/Crashing.py`)**:
  - `CRASH_ADAPTIVE_BOX_FILTER`: Resolution-relative box size filtering (`CRASH_ADAPTIVE_BOX_FRACTION`, default 0.04) resolving distant camera misses.
  - `CRASH_DISTANCE_FACTOR`: Configurable inter-vehicle collision radius (default: 0.25).
  - `CRASH_SINGLE_VEHICLE`: Abrupt deceleration anomaly detection (`CRASH_SINGLE_DECEL_THRESHOLD`) for single-vehicle impacts.
  - `CRASH_CLASSIFIER_THRESHOLD`: Tunable ViF + SVM decision threshold (default: 0.50).
  - Strict 100% legacy byte-for-byte behavioral parity maintained when flags are left disabled.
- **Frontend Trace Drawer & Operator Explainability (`frontend/src/pages/CameraFeeder.tsx`)**:
  - Interactive **Why alerted** / **Why no alert** drawer displaying candidate drop counts, maximum classifier score vs. threshold, and primary cause taxonomy.
  - Active configuration banner displaying enabled detector and geometry flags.
  - Added `label_source`, `cause_category`, and trace summaries to Batch Test Results table and CSV export.
- **Held-Out Evaluation Suite (`scripts/evaluate.py`)**:
  - Rigorous evaluation on 45 held-out test clips (24 normal, 21 accident) with 0 camera group leakage and 95% bootstrap confidence intervals.

---

## [2.1.0] - 2026-11-01

### Added
- **Unified Crash Scoring Interface (`argus_ml.scoring`)**:
  - `CrashScorer` formal Python `Protocol` defining `.score(clip: ClipInput) -> ScoreResult` and `.status() -> ScorerStatus`.
  - `VifSvmScorer`: Spatio-temporal violent flow extractor with ONNX Runtime backend and scikit-learn fallback; includes index boundary pad guard to eliminate optical flow crashes.
  - `ConvAEScorer`: Spatio-temporal ConvLSTM Autoencoder (`ConvLSTMED`) anomaly scorer operating via dynamic PyTorch device selection (CPU, CUDA, Apple Silicon MPS).
  - `OnnxClassifierScorer`: Pluggable deep classifier interface for ResNet-50 / external ONNX visual backbones.
  - `CrashEnsemble`: Multi-model decision ensemble supporting `any`, `all`, `majority`, and `weighted` consensus policies.
- **Model Checkpoints and Parity Exports**:
  - `artifacts/models/vif_svm.onnx`: Exact ONNX conversion of legacy `VIF/model-svm1.sav` with 100% numerical decision parity.
  - `artifacts/models/vif_svm_retrained.onnx`: Retrained linear SVM with balanced class weighting and calibrated probabilities ($F_1 = 0.7179$, Recall $= 66.7\%$).
  - `artifacts/checkpoints/convae/best_model.pth`: Trained normal-flow ConvAE checkpoint with early stopping.
  - `artifacts/calibration/convae_calibration.json`: Platt scaling and zero-FAR threshold calibration parameters derived strictly from validation split.
- **Live Pipeline Integration**:
  - Added feature flag `ARGUS_ENABLE_ENSEMBLE` (default: `false`).
  - Wire `CrashEnsemble` into `System/Functions/Crashing.py` when enabled, with automatic fallback and state preservation in `last_model_scores`.
  - Propagated model scores through `JsonEncoder.py`, `JsonDecoder.py`, `Master.py`, and `DatabaseConnection.py`.
  - Added database migration adding `model_scores` column to `CrashFrames` table.
- **Data Engineering & Split Integrity**:
  - Generated `data/manifest.json` indexing 342 CCTV video clips across 5 sources.
  - Partitioned dataset by grouped camera view to guarantee **zero camera leakage** (252 train, 45 val, 45 test).
  - Added temporal sliding window generator and normalization routines in `argus_ml.preprocessing`.
- **Comprehensive Held-Out Evaluation (`docs/evaluation/`)**:
  - Evaluated on 45 held-out test clips (24 normal, 21 accident) on Apple Silicon M5.
  - Generated `metrics_summary.csv` and `report.md` reporting Accuracy, Precision, Recall, $F_1$ (with 95% bootstrap confidence intervals), PR-AUC, ROC-AUC, p50/p95 latency, and FPS.
- **Frontend Alignment & Operator UI**:
  - Navbar **Models Status Indicator** and accessible popover detailing active policies, versioning, and calibration dates.
  - Added visual `DEV` badge warnings in Navbar popover and `ModelScoreBreakdown` when dev smoke checkpoints are detected.
  - Synchronized `IncidentSearch` client-side consensus filtering and table agreement badges (`2/3 agree`).
  - Enhanced simulated alert publisher (`scripts/fake_alert_publisher.py`) with rich multi-model scores.
- **Documentation & Compliance**:
  - Created standardized model cards for `vif_svm` (`docs/model_cards/vif_svm.md`) and `convae` (`docs/model_cards/convae.md`).
  - Expanded `THIRD_PARTY_NOTICES.md` with complete attribution for DoTA, ConvLSTM, Horn-Schunck, MOSSE, and OpenCV cascades.
  - Documented feature flag reference and training workflows in `README.md`.

### Changed
- Concurrency hardening in `System/Database/DatabaseConnection.py`: replaced per-connection `PRAGMA journal_mode=WAL;` with idempotent initialization check and raised SQLite `busy_timeout` to 15,000 ms to eliminate database lock errors under concurrent traffic.
- Preserved strict byte-for-byte legacy output equivalence when `ARGUS_ENABLE_ENSEMBLE=false` (verified by regression test).

### Fixed
- Fixed index out of bounds error in legacy VIF optical flow processing when frame count satisfies `len(frames) % 6 == 3`.
- Fixed scikit-learn 1.9+ deprecation warning for `probA_` and `probB_` probability calibration attributes.
- Fixed `zmq_listener.py` notification parser to cleanly extract and forward nested `MODEL_SCORES` payloads.

---

## [2.0.0] - 2026-10-28

### Added
- Modern React 19 + Vite + TypeScript web interface in `frontend/`.
- FastAPI asynchronous bridge in `backend/` exposing REST endpoints and WebSocket alert feeds.
- FFmpeg video transcoding and thumbnail extraction pipeline for H.264 streaming.
- Incident review queue, search archive, and camera feeder upload studio.
- Headless orchestration via `Makefile` (`make dev`, `make check`, `make stop`).

---

## [1.0.0] - 2021-12-01

### Added
- Initial release of Argus distributed computer vision accident detection pipeline.
- Four-stage CV topology: YOLO vehicle detection, MOSSE tracking with TCFI, crash estimation filtering, and VIF+SVM classification.
- Presented at 2021 17th International Computer Engineering Conference (ICENCO).

