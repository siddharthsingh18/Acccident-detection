# Changelog

All notable changes to the Argus road-accident detection platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
