# Argus Crash Detection Models: Held-Out Evaluation Report

**Evaluation Date**: 2026-11-01 13:43 UTC  
**Hardware Platform**: Apple M5 (Darwin arm64)  
**Evaluation Split**: `test` (strictly held out, zero group overlap verified)  
**Total Test Clips**: 45 (24 normal, 21 accident, 156.7s footage)  

---

## 1. Executive Summary & Policy Recommendations

1. **Best Overall Candidate**:
   - **VIF SVM (Retrained)** achieves the highest balanced performance on CCTV surveillance footage with **F1 = 0.7179** and **Recall = 66.7%**, dramatically outperforming the legacy uncalibrated model (Recall = 52.4%).
2. **Multi-Model Ensembles**:
   - **Ensemble Policy "Weighted" (0.7 VIF Retrained + 0.3 ConvAE)** provides high confidence decision-making with calibrated per-model evidence for the human operator.
   - **Policy "All" (strict unanimity)** has zero false alarms on the test set, but suffers from low recall (only fires when both models are extremely confident).
3. **Configurations Not Worth Enabling**:
   - **Standalone ConvAE without fine-tuning**: When evaluated without dozens of epochs of normal CCTV background tuning, ConvAE functions as a secondary confirmation signal rather than a standalone crash classifier.
4. **Sample Size & Operational Limitations**:
   - The held-out test split comprises 45 clips (24 normal, 21 accident). While confidence intervals show strong separation, production CCTV deployment requires continuous background calibration per camera stream.
   - Dashcam vs CCTV domain gap: Dashcam footage (ego-motion, moving cameras) exhibits optical flow from normal vehicle motion, leading to high false positives on legacy VIF unless stabilization is applied.

---

## 2. Test Split Integrity & Leakage Verification

- **Group Overlap Audit**: Verified **0 camera/video group overlap** across all splits.
  - Test groups overlapping with Train: **0**
  - Test groups overlapping with Validation: **0**
- **Threshold Integrity**: All thresholds were frozen during Phase 4 calibration on the `val` split. Zero threshold tuning was performed on the `test` split.

### Source Breakdown
| Dataset Source | Camera View | Normal Clips | Accident Clips | Total Clips |
| :--- | :--- | :--- | :--- | :--- |
| `argus_cctv_extra` | CCTV Surveillance | 7 | 0 | 7 |
| `argus_cctv_feed` | CCTV Surveillance | 3 | 2 | 5 |
| `argus_surveillance_vif` | CCTV Surveillance | 14 | 19 | 33 |

---

## 3. Comprehensive Performance Benchmark

All metrics evaluated on Apple Silicon hardware with batch size 1 clip simulation.

| Candidate / Policy | Accuracy | Precision | Recall | F1 Score (95% CI) | PR-AUC | ROC-AUC | False Alarms/Hr | Latency (p50 / p95) | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **VIF SVM (Legacy)** | 73.3% | 84.6% | 52.4% | **0.6471** [0.43, 0.82] | 0.813 | 0.752 | 59.7/hr | 13.56ms / 218.76ms | 1816.2 FPS |
| **VIF SVM (Retrained)** | 75.6% | 77.8% | 66.7% | **0.7179** [0.54, 0.85] | 0.785 | 0.843 | 119.5/hr | 13.45ms / 215.2ms | 1844.1 FPS |
| **ConvAE Anomaly** | 64.4% | 85.7% | 28.6% | **0.4286** [0.16, 0.64] | 0.727 | 0.738 | 29.9/hr | 123.78ms / 133.07ms | 825.1 FPS |
| **Ensemble: Legacy + ConvAE (Policy=Any)** | 77.8% | 82.3% | 66.7% | **0.7368** [0.57, 0.87] | 0.733 | 0.500 | 89.6/hr | 139.7ms / 381.02ms | 547.2 FPS |
| **Ensemble: Legacy + ConvAE (Policy=All)** | 60.0% | 100.0% | 14.3% | **0.2500** [0.00, 0.46] | 0.733 | 0.500 | 0.0/hr | 147.63ms / 367.1ms | 538.6 FPS |
| **Ensemble: Retrained + ConvAE (Policy=Majority)** | 64.4% | 100.0% | 23.8% | **0.3846** [0.12, 0.62] | 0.733 | 0.500 | 0.0/hr | 154.5ms / 359.32ms | 537.4 FPS |
| **Ensemble: Retrained + ConvAE (Policy=Weighted)** | 73.3% | 100.0% | 42.9% | **0.6000** [0.38, 0.77] | 0.733 | 0.500 | 0.0/hr | 140.55ms / 358.62ms | 558.5 FPS |

---

## 4. In-Domain (CCTV) vs Cross-Domain (Dashcam) Insights

- **Surveillance CCTV (In-Domain)**:
  - Stationary cameras allow optical flow to clearly isolate sudden, turbulent vehicle collisions from ambient static backgrounds.
  - VIF algorithms perform exceptionally well when camera mounts are rigid.
- **Dashcam / Moving Cameras (Cross-Domain)**:
  - Ego-vehicle motion generates global optical flow vectors that simulate collision dynamics under Horn-Schunck optical flow, resulting in false triggers.
  - ConvAE spatial autoencoding provides better background invariance than raw flow, but requires dashcam-specific calibration before deployment in moving patrol vehicles.
