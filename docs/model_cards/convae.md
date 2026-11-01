# Model Card: ConvAE Spatio-Temporal Convolutional Autoencoder

## Model Details
- **Model Name**: ConvLSTM Encoder-Decoder Spatio-Temporal Autoencoder (`convae`)
- **Model Version**: `v0.9.0` (`artifacts/checkpoints/convae/best_model.pth`)
- **Model Architecture**: `ConvLSTMED(SimpleNamespace(mode='gray'))`
  - 2D Convolutional Spatial Encoder ($1 \to 128 \to 64 \to 64$ feature maps)
  - Bi-directional Spatio-Temporal ConvLSTM Bottleneck Cells ($3 \times 3$ kernel)
  - 2D Transposed Convolutional Spatial Decoder ($64 \to 64 \to 128 \to 1$)
  - Output Activation: Sigmoid / Tanh reconstruction
- **Model Type**: Semi-supervised / Unsupervised Reconstruction Error Anomaly Detector (PyTorch).
- **Date**: November 2026
- **License**: MIT License (adapted from DoTA / ConvLSTM PyTorch)
- **Frameworks**: PyTorch 2.x (`torch.nn`), torchvision, NumPy. Optional dependency (`argus[ml]`).

---

## Intended Use
- **Primary Intended Uses**: Secondary anomaly verification in stationary roadway CCTV feeds. The model learns normal spatio-temporal representations of continuous vehicular flow; deviations (such as sudden trajectory stops, lateral skid collisions, or debris) yield elevated pixel reconstruction Mean Squared Error (MSE).
- **Primary Intended Users**: Surveillance monitoring operations using multi-model voting ensembles to minimize false dispatches.
- **Out-of-Scope Uses**:
  - Standalone single-model trigger without an ensemble: ConvAE has high precision ($85.7\%$) but conservative recall ($28.6\%$). It is engineered to operate in conjunction with flow classifiers (such as `vif_svm`).
  - Mobile or body-worn cameras: Ego-motion violates the static background reconstruction hypothesis and requires ego-motion compensation.

---

## Input Pipeline & Preprocessing
1. **Input Video**: 30-frame clip at original resolution.
2. **Temporal Windowing**: 5-frame temporal sliding windows with stride 1.
3. **Resizing & Normalization**: Spatial dimensions resized to $128 \times 128$ pixels, converted to grayscale, and normalized to range $[0.0, 1.0]$.
4. **Tensor Format**: Tensor shape `(Batch=1, Channels=1, Time=5, Height=128, Width=128)`.
5. **Anomaly Score Extraction**:
   $$\text{MSE}(X, \hat{X}) = \frac{1}{T \cdot H \cdot W} \sum_{t=1}^T \sum_{h=1}^H \sum_{w=1}^W (X_{t,h,w} - \hat{X}_{t,h,w})^2$$
   The clip anomaly score is the peak window error: $S = \max_{w} \text{MSE}_w$.

---

## Training & Calibration Methodology

### 1. Normal-Only Training
- **Training Set**: 176 normal CCTV surveillance clips (filtered to exclude all collision footage).
- **Loss Function**: Mean Squared Error (MSE) between original and reconstructed spatio-temporal volumes.
- **Optimizer**: Adam ($\text{lr} = 10^{-4}$, weight decay $10^{-5}$).
- **Validation**: Monitored reconstruction error on normal validation clips; best checkpoint saved via early stopping to `artifacts/checkpoints/convae/best_model.pth`.

### 2. Validation Split Calibration
Calibrated strictly on the held-out `val` split (19 normal, 26 accident clips) via `scripts/calibrate.py`:
- **Raw Reconstruction Error Range**:
  - Minimum normal error ($\min$): $0.103928$
  - Maximum collision error ($\max$): $0.414069$
- **Zero-FAR Threshold**: $0.400628$ raw MSE (mapped to calibrated normalized score of $0.9567$).
- **Platt Scaling Logistic Calibration**:
  $$P(\text{crash} \mid s) = \frac{1}{1 + \exp(-(a \cdot s + b))}, \quad a = 0.1842, \; b = 0.2661$$
- **Calibration Artifact**: Persisted at `artifacts/calibration/convae_calibration.json` and loaded dynamically by `ConvAEScorer`.

---

## Evaluation on Held-Out Test Split

All metrics measured on Apple Silicon M5 (macOS Darwin arm64) using strictly held-out `test` split (45 clips, 156.7 seconds, zero camera overlap):

| Metric | ConvAE Anomaly Model | Ensemble (Legacy VIF + ConvAE, Any) | Ensemble (Retrained VIF + ConvAE, Weighted) |
| :--- | :--- | :--- | :--- |
| **Accuracy** | 64.4% | **77.8%** | 73.3% |
| **Precision** | **85.7%** | 82.3% | **100.0%** |
| **Recall (Sensitivity)** | 28.6% | **66.7%** | 42.9% |
| **F1 Score** | 0.4286 (95% CI: [0.16, 0.64]) | **0.7368** (95% CI: [0.57, 0.87]) | 0.6000 (95% CI: [0.38, 0.77]) |
| **PR-AUC** | 0.727 | 0.733 | 0.733 |
| **ROC-AUC** | 0.738 | 0.500 | 0.500 |
| **False Alarms per Hour** | **29.9 / hr** | 89.6 / hr | **0.0 / hr** |
| **Inference Latency (p50)** | 123.78 ms | 139.70 ms | 140.55 ms |
| **Inference Latency (p95)** | 133.07 ms | 381.02 ms | 358.62 ms |
| **Throughput** | 825.1 FPS | 547.2 FPS | 558.5 FPS |

---

## CCTV vs Dashcam Domain Limitations
- **Surveillance CCTV (In-Domain)**:
  - Static camera perspective allows background features (road pavement, guardrails, lane markings) to reconstruct cleanly. Moving vehicles that crash or spin generate distinct structural anomalies.
- **Dashcam Driving Videos (Cross-Domain)**:
  - Dashcam videos exhibit dynamic ego-motion, fluctuating horizon lines, and moving perspective. An autoencoder trained on CCTV will treat normal driving turns as anomalies. Dashcam deployment requires retraining on ego-stabilized driving footage.

---

## Operational Safeguards & Human Verification
> [!WARNING]
> ConvAE anomaly scores indicate reconstruction divergence, which may be triggered by non-crash events such as sudden pedestrian crossings, large shadows, debris blowing across lanes, or camera lens obstructions.
> **Human verification is mandatory before taking any operational or emergency response action.**

