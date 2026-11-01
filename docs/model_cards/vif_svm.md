# Model Card: Violent Flows (VIF) + Support Vector Machine (SVM)

## Model Details
- **Model Name**: Violent Flows + Linear SVM Crash Classifier (`vif_svm`)
- **Model Versions**:
  - `v1.0.0-legacy` (`VIF/model-svm1.sav`, converted to ONNX at `artifacts/models/vif_svm.onnx`)
  - `v1.1.0-retrained` (`artifacts/models/vif_svm_retrained.onnx`)
- **Model Type**: Spatio-temporal motion flow feature extractor (ViF) coupled with a linear Support Vector Classifier (scikit-learn / ONNX Runtime).
- **Date**: November 2026
- **License**: MIT License
- **Frameworks**: ONNX Runtime (`onnxruntime`), scikit-learn (`sklearn.svm.SVC`), NumPy, OpenCV.

---

## Intended Use
- **Primary Intended Uses**: Real-time traffic collision detection from fixed, stationary closed-circuit television (CCTV) cameras overlooking roadways, intersections, and highways.
- **Primary Intended Users**: Traffic management centers, municipal surveillance operators, and emergency service dispatchers for decision-support alerting.
- **Out-of-Scope Uses**:
  - Dashcam or mobile cameras: Global camera ego-motion induces large optical flow vectors across the frame, leading to excessive false positives.
  - Autonomous emergency braking or automated legal fault assignment: The model is strictly an advisory screening filter and requires human operator verification.

---

## Input Pipeline & Preprocessing
1. **Input**: Sequence of grayscale video frames (minimum 15 frames, default 30 frames).
2. **Subsampling**: Temporal subsampling factor of $N=3$ (every 3rd frame evaluated).
3. **Motion Flow**: Horn-Schunck optical flow calculation between consecutive subsampled frames.
4. **ViF Histogram Generation**: Mean optical flow magnitudes computed across a $4 \times 4$ spatial grid into 21-bin histograms (producing a 336-dimensional feature vector).
5. **Boundary Guard**: Sequences where `len(frames) % 6 == 3` are padded by 1 frame to prevent index boundary truncation in optical flow difference calculations.

---

## Training Data & Provenance
- **Dataset**: CCTV traffic surveillance footage (`argus_surveillance_vif`, `argus_cctv_extra`, `argus_cctv_feed`).
- **Splits**: Grouped camera view partitioning ensuring **zero camera leakage** across splits:
  - **Train**: 252 clips (176 normal, 76 accident)
  - **Validation**: 45 clips (19 normal, 26 accident)
  - **Test (Held-Out)**: 45 clips (24 normal, 21 accident)
- **Retraining Modifications**:
  - `v1.0.0-legacy`: Originally trained with unweighted loss, leading to low accident recall ($52.4\%$) due to class imbalance.
  - `v1.1.0-retrained`: Trained using `class_weight='balanced'`, Platt scaling probability calibration ($P(\text{crash} \mid x) = \frac{1}{1 + \exp(Ax + B)}$), and exported to ONNX format with 100% numerical parity.

---

## Evaluation on Held-Out Test Split

All metrics measured on Apple Silicon M5 (macOS Darwin arm64) using strictly held-out `test` split (45 clips, 156.7 seconds, zero camera overlap):

| Metric | Legacy VIF+SVM (`v1.0.0`) | Retrained VIF+SVM (`v1.1.0`) |
| :--- | :--- | :--- |
| **Accuracy** | 73.3% | **75.6%** |
| **Precision** | **84.6%** | 77.8% |
| **Recall (Sensitivity)** | 52.4% | **66.7%** (+14.3%) |
| **F1 Score** | 0.6471 (95% CI: [0.43, 0.82]) | **0.7179** (95% CI: [0.54, 0.85]) |
| **PR-AUC** | **0.813** | 0.785 |
| **ROC-AUC** | 0.752 | **0.843** (+0.091) |
| **False Alarms per Hour** | **59.7 / hr** | 119.5 / hr |
| **Inference Latency (p50)** | **13.56 ms** | **13.45 ms** |
| **Inference Latency (p95)** | 218.76 ms | 215.20 ms |
| **Throughput** | 1816.2 FPS | **1844.1 FPS** |

---

## Factors & Caveats
- **Fixed Mount Assumption**: ViF assumes optical flow changes originate from object movements, not camera shaking or panning. Windy conditions causing pole vibration may increase false alarm rates.
- **Extreme Weather & Glare**: Heavy snowfall, rain streaks on camera housing, or direct sun glare into the lens can degrade optical flow fidelity.
- **Mandatory Human Verification**: Model scores are algorithmic screening estimates, not confirmed facts. Human operators must inspect video replays prior to dispatching emergency responders.
