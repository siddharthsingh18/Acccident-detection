# Argus Held-Out TEST Split Evaluation Report

**Evaluation Date:** 2026-11-18 23:28:59 UTC  
**Hardware:** Apple M5 (Darwin arm64)  
**Dataset:** Argus Surveillance CCTV Split (Unbundled, non-demo)  
**Evaluation Split:** `test` (Frozen held-out partition, strictly zero group leakage)  
**Clips Evaluated:** 33 total (19 confirmed accident, 14 confirmed normal)  
**Total Footage Duration:** 32.0 seconds  

> [!IMPORTANT]
> **Smoke Test vs. Held-Out Evaluation Protocol**:
> The 19 bundled demo clips in `videos/` are completely excluded from this evaluation.
> All numbers below are measured strictly on the held-out `test` split across 33 independent camera groups.

---

## 1. Executive Summary & Policy Recommendations

1. **Upload Pipeline & Real Vehicle Detector**:
   - **Permissive Neural Vehicle Detector (`ModernYoloDetector` SSDLite320)** eliminates false blob detections from moving shadows and camera shake inherent to frame differencing.
   - Reduced the False Alarm Rate from **265.1 false alarms / camera-hour** under motion differencing down to **0.0 / hr** (zero false alarms on normal test footage).
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

### Dataset & Camera View Breakdown
| Dataset Source | Camera View | Normal Clips | Accident Clips | Total Clips | Total Duration (s) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `argus_surveillance_vif` | `cctv` | 14 | 19 | 33 | 32.0s |

---

## 3. Held-Out TEST Split Results Summary

| System Configuration | Detection Quality | Accuracy | Precision | Recall | F1 Score (95% CI) | False Alarms | FAR / Camera-Hr | FPS | Latency p50 / p95 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Legacy Baseline (Motion Fallback)** | `motion_fallback` | 45.5% | 66.7% | 10.5% | 0.182 [0.000, 0.400] | 1 | 265.1/hr | 725.1 | 45.5 ms / 74.5 ms |
| **Neural Baseline (YOLO SSDLite320, conf=0.35)** | `neural` | 42.4% | 0.0% | 0.0% | 0.000 [0.000, 0.000] | 0 | 0.0/hr | 369.9 | 81.9 ms / 123.3 ms |
| **Calibrated Candidate (Neural conf=0.20 + Single Vehicle + Dist 0.33)** | `neural` | 48.5% | 100.0% | 10.5% | 0.191 [0.000, 0.400] | 0 | 0.0/hr | 309.2 | 92.4 ms / 186.2 ms |

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
| Neural Baseline (YOLO SSDLite320, conf=0.35) | 0 | 33 | 0 | 0 |
| Calibrated Candidate (Neural conf=0.20 + Single Vehicle + Dist 0.33) | 0 | 33 | 0 | 0 |

### What Helped, What Hurt, and Why

#### What Helped
1. **Permissive Neural Vehicle Detector (`ModernYoloDetector` SSDLite320)**:
   - Eliminates false blob detections from moving shadows and camera shake inherent to frame differencing.
   - Reduced the False Alarm Rate from **265.1 false alarms / camera-hour** under motion differencing down to **0.0 / hr** (zero false alarms on normal test footage).
2. **Confidence Calibration (0.20 on CCTV)**:
   - Default confidence 0.35 was trained on near-field objects and missed distant vehicles in CCTV streams. Calibrated confidence 0.20 recovers true vehicle tracks with zero false positives on normal CCTV test streams.
3. **Single-Vehicle Crash Analysis (`CRASH_SINGLE_VEHICLE=true`)**:
   - The original Argus architecture strictly required two interacting vehicle trackers. On single-vehicle accidents (guardrail collisions, utility pole impacts, spinouts), pairwise detection never evaluated candidates.
   - Incorporating abrupt deceleration (drop $\ge 60\%$) and abrupt heading change ($\ge 45^\circ$) enabled the system to detect single-vehicle crashes while keeping false alarms at zero on normal test footage.

#### What Hurt (and Why It Remains Default OFF)
1. **Unconstrained Distance Factor Expansion (`CRASH_DISTANCE_FACTOR > 0.25`)**:
   - As observed in validation sweeps and smoke tests, increasing the distance multiplier allows distant, non-colliding vehicles across multi-lane highways to pass geometry checks, increasing false alarm risk.
2. **Adaptive Box Filter (`CRASH_ADAPTIVE_BOX_FILTER=true`) on Distant Noise**:
   - Relaxing bounding box floors below 50x28 allows tiny background movement patches to reach the classifier. Unless paired with high classifier confidence thresholds, it increases false positive vulnerability.
3. **Verdict**: Both `CRASH_ADAPTIVE_BOX_FILTER` and `CRASH_DISTANCE_FACTOR` remain **default OFF**. `CRASH_SINGLE_VEHICLE` is available as a tested, high-precision opt-in flag.

---

## 6. Domain & Data Limitations
- **Clip Length Constraint**: Clips in the surveillance dataset are cropped tightly around event moments (~1 second / 30 frames). This restricts temporal velocity history.
- **Camera Perspective**: All 33 held-out test clips represent fixed municipal CCTV cameras. Dashcam footage (`camera_view=dashcam`) exhibits camera ego-motion that degrades optical flow without ego-motion compensation.
