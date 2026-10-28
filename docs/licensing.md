# Open-Source Object Detection Model Licensing Evaluation

**Project**: Argus Road-Accident Detection & Surveillance System  
**Repository License**: **MIT License**  
**Date**: October 2026  
**Objective**: Evaluate vehicle detection frameworks for real-time video inference without violating or contaminating Argus's permissive MIT license.

---

## 1. Candidate Comparison Matrix

| Framework / Model | Upstream License | MIT Compatibility | Dependencies | Strengths | Drawbacks / Risks |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ultralytics YOLO (v8 / v11)** | **GNU AGPL v3.0** (or Commercial) | ❌ **High Risk / Incompatible** without Enterprise License | `ultralytics`, `torch` | High mAP, active community, state-of-the-art accuracy | **AGPL-3.0 is viral over network interactions** (Section 13). Exposing an AGPL service via FastAPI/WebSocket requires open-sourcing the entire derivative stack under AGPL-3.0 unless an enterprise commercial license is purchased. |
| **YOLOX (Megvii)** | **Apache 2.0** | ✅ **Compatible** | `torch`, `torchvision` (or ONNX) | Anchor-free, fast CPU/GPU inference, permissive license | Smaller standalone developer community than Ultralytics |
| **RT-DETR (Baidu / Lyuwenyu)** | **Apache 2.0** | ✅ **Compatible** | `torch` / `onnxruntime` | Transformer-based SOTA accuracy, real-time latency | Higher parameter count; heavier on lower-end CPU devices |
| **torchvision Detection Models** (`fasterrcnn`, `ssdlite320_mobilenet_v3`) | **BSD 3-Clause** | ✅ **Fully Compatible** | `torch`, `torchvision` | Zero extra dependencies (ships with PyTorch), built-in COCO weights with SHA-256 validation | SSDLite has lower mAP on small distant vehicles; Faster R-CNN is slower on CPU |
| **ONNX Runtime (Open Neural Network Exchange)** | **MIT License** | ✅ **Fully Compatible** | `onnxruntime`, `numpy`, `opencv-python` | High-performance multi-threaded CPU inference on x86 and Apple Silicon; decoupled from training framework | Model weights must be exported or downloaded as `.onnx` |

---

## 2. Detailed License Analysis

### A. The Ultralytics AGPL-3.0 Challenge
Ultralytics transitioned from GPL to **AGPL-3.0** starting with YOLOv8. Key stipulations:
1. **Network Use Clause (Section 13)**: If a user interacts with modified or unmodified AGPL software over a computer network (e.g., Argus's FastAPI REST endpoints or WebSocket alerts), the provider must offer access to the Corresponding Source to all network users.
2. **License Contamination**: Incorporating `from ultralytics import YOLO` directly into a core module under an MIT-licensed repository creates legal ambiguity and imposes AGPL requirements on downstream commercial or municipal users.
3. **Verdict**: **Do NOT bundle or require `ultralytics` as a mandatory dependency.** If users have purchased an enterprise commercial license or accept AGPL terms, it may be supported strictly through an isolated opt-in adapter.

### B. Apache 2.0 and BSD-3 Options
Both **Apache 2.0** (YOLOX, RT-DETR) and **BSD 3-Clause** (`torchvision`) are fully compatible with the MIT license. They permit commercial distribution, sublicensing, and cloud hosting without copyleft reciprocal source disclosure requirements.

### C. ONNX Runtime Model Decoupling
By targeting **ONNX Runtime** (MIT license):
- The model graph and weights (`.onnx`) are executed via `onnxruntime`.
- No Python code from copyleft frameworks is imported or executed at runtime.
- Weights are verified via cryptographic SHA-256 hashes prior to loading.

---

## 3. Architecture Recommendation for Argus

1. **Default Strategy**:
   - Keep `DETECTOR=legacy` (`boxes/*.txt` reading) as the default until explicitly toggled.
2. **Permissive Modern Detector**:
   - Implement a modular `DetectorInterface` in `System/Functions/Detection.py`.
   - Provide **Torchvision / ONNX YOLOX / MobileNet-SSD** as the built-in modern detector (`DETECTOR=yolo` / `DETECTOR=torchvision`) under Apache-2.0 / BSD / MIT terms.
3. **Model Weight Verification**:
   - Provide `scripts/download_models.py` which checks SHA-256 integrity, prints model licensing terms, and saves models to `models/`.
4. **Fallback Mechanism**:
   - If modern model weights are not found and `DETECTOR=yolo` is active, cleanly fall back to `MotionFallback` with an explicit warning in logs and in the UI feed status (`"low-quality detection mode"`).
