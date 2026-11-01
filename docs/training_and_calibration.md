# Model Training and Calibration Guide

This document explains how to reproduce training, calibrate anomaly detection thresholds, retrain the legacy VIF+SVM model, and manage artifact checkpoints in Argus.

---

## 1. Directory Structure & Artifact Layout

All binary weights, checkpoint files, calibrations, and feature caches are stored under `artifacts/` and `data/` and are strictly ignored by git (`.gitignore`).

```
artifacts/
├── calibration/
│   └── convae_calibration.json     # Calibrated thresholds & Platt scaling parameters
├── checkpoints/
│   └── convae/
│       ├── best_model.pth          # PyTorch state_dict of best ConvAE checkpoint
│       ├── best_model.json         # Checkpoint metadata (hash, hardware, metrics, git commit)
│       ├── smoke_checkpoint.pth    # Lightweight dev-only checkpoint
│       └── smoke_checkpoint.json   # Dev smoke test metadata (dev_only: true)
└── models/
    ├── vif_svm.onnx                # Default VIF+SVM ONNX model (exported with parity verification)
    ├── vif_svm_retrained.onnx      # Class-balanced retrained VIF+SVM ONNX model
    └── resnet_onnx.onnx            # Pluggable external classifier slot (optional)
```

### Where to Place Pretrained Models
- **ConvAE**: Place weights file at `artifacts/checkpoints/convae/best_model.pth` (must be a PyTorch `state_dict` loadable with `torch.load(..., weights_only=True)`), or set the environment variable:
  ```bash
  export CONVAE_CHECKPOINT_PATH="/path/to/custom_convae.pth"
  ```
- **External Classifier (ResNet ONNX)**: Place the ONNX model at `artifacts/models/resnet_onnx.onnx` and provide its sidecar metadata at `artifacts/models/resnet_onnx.json`.

---

## 2. ConvAE Anomaly Detection Training

ConvAE (`ConvLSTMED`) is trained in an unsupervised manner strictly on normal CCTV clips (`split == 'train'` and `label == 'normal'`). It learns the nominal spatio-temporal dynamics of traffic flows; collisions and abnormal interactions produce elevated reconstruction errors.

### Training Configurations
Configurations are located in `configs/`:
- `configs/convae_smoke.json`: Fast run (2 epochs, 8 samples) for testing and CI.
- `configs/convae_full.json`: Full training configuration (20 epochs, batch size 8, learning rate 1e-4, patience 5).

### Commands

1. **Estimate Training Time on Local Hardware**:
   ```bash
   .venv/bin/python scripts/train_convae.py --config configs/convae_full.json --estimate-only
   ```
   *Benchmarked on Apple M5 (MPS): ~89.6s/epoch, throughput 4.02 windows/s, estimated total ~29.9 minutes for 20 epochs.*

2. **Run Smoke Training**:
   ```bash
   .venv/bin/python scripts/train_convae.py --smoke
   ```

3. **Run Full Training**:
   ```bash
   .venv/bin/python scripts/train_convae.py --config configs/convae_full.json
   ```

Checkpoints are saved as PyTorch `state_dict` objects to `artifacts/checkpoints/convae/best_model.pth` alongside `best_model.json`.

---

## 3. Threshold Calibration (`scripts/calibrate.py`)

Calibration computes the operating threshold and maps raw reconstruction MSE errors to `[0.0, 1.0]`.

### Ground Rules for Calibration
- **Validation Split Only**: Calibration strictly uses the `val` split (19 normal CCTV clips, 26 accident clips). The `test` split is never loaded or tuned against.
- **Target False Alarm Rate**: Default is 1 false alarm per camera-hour. The script evaluates normal footage duration and calculates empirical thresholds.
- **Platt Scaling**: Fits a logistic regression mapping from reconstruction error to estimated accident probability.

### Running Calibration
```bash
.venv/bin/python scripts/calibrate.py --target-far 1.0
```

Calibration outputs are saved to `artifacts/calibration/convae_calibration.json`.

---

## 4. Retraining VIF+SVM (`scripts/retrain_svm.py`)

The legacy crash detector relies on Violent Flows (VIF) optical flow histograms (304 dimensions) fed into a linear SVM.

### Retraining with Class Balancing
The original SVM had an unbalanced recall (40.0% recall on the validation split). Running `scripts/retrain_svm.py`:
1. Recomputes VIF features across all train (241 valid) and val (43 valid) clips.
2. Trains a new `SVC(kernel='linear', class_weight='balanced', probability=True, random_state=42)`.
3. Evaluates both the old legacy model and the retrained model side-by-side on the validation set.
4. Exports the retrained model to ONNX (`artifacts/models/vif_svm_retrained.onnx`) with 100% parity verification.

### Running Retraining
```bash
.venv/bin/python scripts/retrain_svm.py
```

To replace the default ONNX model (`artifacts/models/vif_svm.onnx`):
```bash
.venv/bin/python scripts/retrain_svm.py --replace
```

### Measured Validation Split Results (43 clips: 18 normal, 25 accident)
| Metric | Old Model (`model-svm1.sav`) | Retrained Model | Difference |
| :--- | :--- | :--- | :--- |
| **Accuracy** | 0.5581 (55.8%) | 0.6512 (65.1%) | **+9.3%** |
| **Precision** | 0.7143 | 0.6923 | -2.2% |
| **Recall** | 0.4000 (40.0%) | 0.7200 (72.0%) | **+32.0%** |
| **F1 Score** | 0.5128 | 0.7059 | **+19.3%** |

