# Argus Surveillance Ops Frontend

The frontend for Argus is a dark control-room web application built with **React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, React Hook Form, and Zod**. It connects in real-time to the Argus computer vision pipeline and FastAPI bridge.

---

## Key Features

1. **Live Surveillance Dashboard (`/`)**:
   - Real-time accident alert stream via WebSocket (`/ws/alerts`).
   - Incident cards with review status and compact **Model Agreement Badges** (e.g., `2/3 agree`).
   - Malformed ML metadata falls back gracefully to `null` without dropping safety alerts.
   - Audio sirens and visual alert notifications with dismiss controls.

2. **Detection Studio & Camera Feeder (`/feeder`)**:
   - Dual-view interface: Input video preview and analyzed output stream with crash annotations.
   - **Detected Event Timeline**: starting frame, crash timestamp, location, and telemetry record.
   - **Model Score Breakdown**: comprehensive scoring table with individual model confidence bars.
   - **Compare Models Toggle**: side-by-side inspection cards for each active scorer.
   - **Degraded Mode Advisory Banner**: alerts operators when processing with fewer models than configured.
   - Honest indicator: *"Per-frame trajectory scores not available for legacy pipeline runs"*.

3. **Surveillance Records Archive (`/search`)**:
   - Temporal, regional, and review-status filters synchronized with URL query params.
   - **Models Agree Filter**: filter by `Any (all records)`, `All available models flagged`, or `Only one model flagged`.
   - Client-side filtering notice when filtering loaded search records.
   - CSV export including per-model scores, fired flags, and ensemble decisions.

4. **Incident Review Queue (`/review`)**:
   - Operator triage interface for unreviewed crash incidents.
   - Integrated `<ModelScoreBreakdown />` and keyboard shortcuts (`C` = Confirm, `F` = False Alarm).

5. **Models Status Popover (Navbar)**:
   - Navbar status pill displaying ensemble health:
     - 🟢 **Models OK**: all active scorers available and ensemble healthy.
     - 🟡 **Degraded (legacy only)**: running with fewer models than configured.
     - ⚪ **Models Offline**: status endpoint unreachable.
   - Accessible popover showing active ensemble policy, scorer versions, training datasets, calibration dates, and failure reasons.

6. **Dev Component Showcase (`/dev/components`)**:
   - Active only during development (`import.meta.env.DEV`).
   - Showcases `<ModelScoreBreakdown />` in all 5 states: consensus (all-agree), split-decision, one-flagged, degraded, and legacy (null scores).

---

## Machine Learning Ensemble & Scoring

### 1. The Registered Crash Scorers
- **Violent Flows (`vif_svm`)**: Spatio-temporal kinetic flow variance spikes across motion vector regions via Horn-Schunck optical flow and Support Vector Machine.
- **ConvAE Anomaly Model (`convae`)**: Unsupervised spatio-temporal Convolutional Autoencoder irregularity reconstruction error.
- **ResNet-50 Classifier (`resnet_onnx`)**: Pre-trained convolutional deep feature classification (ONNX runtime).

### 2. Ensemble Decision Policies
- **`majority` (default)**: Alert triggers only when a majority of available active scorers classify the sequence as a crash.
- **`any`**: Alert triggers if any single available scorer flags a crash.
- **`all`**: Alert triggers only if all available scorers achieve consensus.
- **`weighted`**: Alert triggers when the weighted sum of calibrated model confidence estimates crosses the configured threshold.

### 3. Understanding "Degraded" Mode
- **What it means**: Degraded mode indicates that one or more configured advanced models (such as ConvAE or ONNX) could not be loaded (e.g., PyTorch extra not installed, weights file missing, or ONNX runtime unavailable).
- **Graceful Fallback**: The Argus pipeline never crashes or stops detecting accidents when degraded. It falls back safely to the baseline VIF+SVM detector.
- **How to resolve**:
  ```bash
  # 1. Install optional ML extra in your virtualenv:
  pip install -e ".[torch]"
  # or: pip install torch torchvision

  # 2. Ensure weights are present:
  python scripts/data/download_dota.py
  ```

### 4. Critical Disclaimer: Estimates, Not Facts

> [!WARNING]
> **Model estimates, not confirmed facts. Human verification required.**
>
> All model scores, agreement counts, and confidence percentages displayed in the Argus frontend are **statistical algorithmic estimates**, not ground truth crash facts. Under no circumstances should a score be interpreted as a literal probability of accident occurrence. A qualified human operator must inspect the video footage before dispatching emergency services.

---

## Development & Testing

```bash
# Run development dev server (port 5173)
npm run dev

# Run Oxlint linter
npm run lint

# TypeScript typecheck and production build
npm run build

# Run Vitest unit tests
npm run test:unit
```
