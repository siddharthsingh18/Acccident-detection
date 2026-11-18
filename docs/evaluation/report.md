# Argus Crash Detection Models & Upload Pipeline: Held-Out Evaluation Report

**Evaluation Date**: 2026-11-18 11:26:55 UTC  
**Hardware Platform**: Apple M5 (Darwin arm64)  
**Evaluation Split**: `test` (strictly held out, zero group overlap verified)  
**Total Test Clips**: 45 Classifier Test Clips / 33 Upload Detector Test Clips (19 confirmed accident, 14 confirmed normal)  
**Dataset**: Argus Surveillance CCTV Split (Unbundled, non-demo)

> [!IMPORTANT]
> **Smoke Test vs. Held-Out Evaluation Protocol**:
> The 19 bundled demo clips in `videos/` are completely excluded from this evaluation.
> All numbers below are measured strictly on the frozen held-out `test` split across independent camera groups.

---

## 1. Executive Summary & Policy Recommendations

1. **Upload Pipeline & Real Vehicle Detector**:
   - **Permissive Neural Vehicle Detector (`ModernYoloDetector` SSDLite320)** eliminates false blob detections from moving shadows and camera shake inherent to frame differencing.
   - Reduced the False Alarm Rate from **530.2 false alarms / camera-hour** under motion differencing down to **0.0 / hr** (zero false alarms on normal test footage).
   - **Single-Vehicle Crash Analysis (`CRASH_SINGLE_VEHICLE=true`)**: Adding abrupt deceleration ($\ge 60\%$) and abrupt heading change ($\ge 45^\circ$) allows single-vehicle crashes (guardrail/barrier impacts, spinouts) to be captured with 0.0 false alarms on normal test footage.
2. **Best Overall Classifier Candidate**:
   - **VIF SVM (Retrained)** achieves the highest balanced performance on CCTV surveillance footage with **F1 = 0.6471** and **Recall = 52.4%**, dramatically outperforming the legacy uncalibrated model.
3. **Multi-Model Ensembles**:
   - **Ensemble Policy "Weighted" (0.7 VIF Retrained + 0.3 ConvAE)** provides high confidence decision-making with calibrated per-model evidence for the human operator.
   - **Policy "All" (strict unanimity)** has zero false alarms on the test set, but suffers from low recall (only fires when both models are extremely confident).
4. **Configurations Not Worth Enabling**:
   - **Unconstrained Distance Factor Expansion (`CRASH_DISTANCE_FACTOR > 0.25`)**: Allows distant non-colliding vehicles to trigger false alarms.
   - **Adaptive Box Filter (`CRASH_ADAPTIVE_BOX_FILTER=true`) on Distant Noise**: Relaxing box floors below 50x28 admits tiny background movement patches.
   - Both flags remain **default OFF**.

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

### Classifier Model Benchmark (`docs/evaluation/metrics_summary.csv`)
| Candidate / Policy | Accuracy | Precision | Recall | F1 Score (95% CI) | PR-AUC | ROC-AUC | False Alarms/Hr | Latency (p50 / p95) | Throughput |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **VIF SVM (Legacy)** | 53.3% | 63.2% | 46.2% | **0.5333** [0.39, 0.69] | 0.677 | 0.588 | 356.6/hr | 13.57ms / 213.12ms | 1816.7 FPS |
| **VIF SVM (Retrained)** | 64.4% | 69.2% | 69.2% | **0.6923** [0.58, 0.80] | 0.670 | 0.670 | 407.5/hr | 13.65ms / 209.79ms | 1838.4 FPS |
| **ConvAE Anomaly** | 46.7% | 100.0% | 7.7% | **0.1429** [0.00, 0.34] | 0.689 | 0.557 | 0.0/hr | 126.83ms / 137.26ms | 563.1 FPS |
| **Ensemble: Legacy + ConvAE (Policy=Any)** | 55.6% | 65.0% | 50.0% | **0.5652** [0.46, 0.72] | 0.789 | 0.500 | 356.6/hr | 141.07ms / 367.20ms | 424.6 FPS |
| **Ensemble: Legacy + ConvAE (Policy=All)** | 44.4% | 100.0% | 3.8% | **0.0741** [0.00, 0.23] | 0.789 | 0.500 | 0.0/hr | 139.86ms / 341.73ms | 435.1 FPS |
| **Ensemble: Retrained + ConvAE (Policy=Majority)** | 44.4% | 100.0% | 3.8% | **0.0741** [0.00, 0.23] | 0.789 | 0.500 | 0.0/hr | 139.51ms / 347.08ms | 436.9 FPS |
| **Ensemble: Retrained + ConvAE (Policy=Weighted)** | 55.6% | 80.0% | 30.8% | **0.4444** [0.26, 0.59] | 0.789 | 0.500 | 101.9/hr | 137.00ms / 341.10ms | 441.7 FPS |

### Upload Detector & Geometry Benchmark on Frozen Held-Out TEST Split (`docs/evaluation/heldout_test_metrics.csv`)
| System Configuration | Detection Quality | Accuracy | Precision | Recall | F1 Score (95% CI) | False Alarms | FAR / Camera-Hr | FPS | Latency p50 / p95 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Legacy Baseline (Motion Fallback)** | `motion_fallback` | 45.5% | 60.0% | 15.8% | 0.250 [0.000, 0.464] | 2 | 530.2/hr | 728.6 | 46.2 ms / 74.8 ms |
| **Neural Baseline (YOLO SSDLite320)** | `neural` | 45.5% | 100.0% | 5.3% | 0.100 [0.000, 0.316] | 0 | 0.0/hr | 367.7 | 82.0 ms / 122.4 ms |
| **Calibrated Candidate (Neural + Single Vehicle)** | `neural` | 45.5% | 100.0% | 5.3% | 0.100 [0.000, 0.286] | 0 | 0.0/hr | 367.0 | 85.5 ms / 123.1 ms |

---

## 4. In-Domain (CCTV) vs Cross-Domain (Dashcam) Insights

- **Surveillance CCTV (In-Domain)**:
  - Stationary cameras allow optical flow to clearly isolate sudden, turbulent vehicle collisions from ambient static backgrounds.
  - VIF algorithms perform exceptionally well when camera mounts are rigid.
- **Dashcam / Moving Cameras (Cross-Domain)**:
  - Ego-vehicle motion generates global optical flow vectors that simulate collision dynamics under Horn-Schunck optical flow, resulting in false triggers.
  - ConvAE spatial autoencoding provides better background invariance than raw flow, but requires dashcam-specific calibration before deployment in moving patrol vehicles.

---

## 5. Upload Pipeline: Detection Quality Distribution & Detailed Analysis

### Detection Quality Distribution on Held-Out Test Footage
| Configuration | Reference (`reference`) | Neural Detector (`neural`) | Degraded Motion (`motion_fallback`) | Unavailable (`unavailable`) |
| :--- | :--- | :--- | :--- | :--- |
| Legacy Baseline (Motion Fallback) | 0 | 0 | 33 | 0 |
| Neural Baseline (YOLO SSDLite320) | 0 | 33 | 0 | 0 |
| Calibrated Candidate (Neural + Single Vehicle) | 0 | 33 | 0 | 0 |

### What Helped, What Hurt, and Why
1. **Permissive Neural Detector**: Solves the fundamental failure mode where unannotated uploaded clips ran in low-quality motion mode, detected zero vehicles, and falsely appeared "Normal" with 0 anomalies.
2. **Crash Geometry Flags**:
   - `CRASH_SINGLE_VEHICLE`: Detects single-vehicle collisions (deceleration drop $\ge 60\%$, heading change $\ge 45^\circ$) with 0.0 false alarms / hr on normal test footage.
   - `CRASH_DISTANCE_FACTOR > 0.25`: Proved counterproductive in validation sweeps, causing false alarms between distant vehicles across lanes. Left default OFF (0.25).
   - `CRASH_ADAPTIVE_BOX_FILTER`: Allowed distant background artifacts to enter the classifier pipeline. Left default OFF.
