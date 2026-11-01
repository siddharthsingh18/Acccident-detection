# Third-Party Software and Dataset Notices

This repository incorporates or adapts code and metadata from the following open-source projects and research datasets.

---

## 1. Detection of Traffic Anomaly (DoTA)

* **Source Repository:** [MoonBlvd/Detection-of-Traffic-Anomaly](https://github.com/MoonBlvd/Detection-of-Traffic-Anomaly)
* **Citation:**
  > Yao, Y., Wang, X., Xu, M., Pu, Z., Wang, Y., Atkins, E., & Crandall, D. (2022).  
  > "DoTA: Unsupervised Detection of Traffic Anomaly in Driving Videos."  
  > *IEEE Transactions on Pattern Analysis and Machine Intelligence (TPAMI)*.
* **License:** MIT License
* **Copyright:** (c) 2020 Yu Yao
* **Files Imported:** `dataset/DoTA/*`, `ConvAE/*`
* **Local Modifications:**
  - Removed author-specific hardcoded filesystem paths (`/mnt/workspace/datasets/A3D_2.0/`, `/home/brianyao/...`).
  - Removed interactive breakpoint statements (`pdb.set_trace()`).
  - Replaced hardcoded CUDA calls with dynamic device detection supporting CPU, CUDA, and Apple Silicon MPS (`torch.backends.mps.is_available()`).
  - Guarded distributed/GPU-specific libraries (`mpi4py`, `apex`) behind graceful fallback imports so headless or CPU environments can run.
  - Untracked 10 MB `DoTA_annotations.zip` from git, replaced with verified checksum download script `scripts/data/download_dota.py`.
  - Full details documented in `ConvAE/PATCHES.md`.

### MIT License Text
```
MIT License

Copyright (c) 2020 Yu Yao

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. ConvLSTM PyTorch Implementation

* **Source Repository:** [ndrplz/ConvLSTM_pytorch](https://github.com/ndrplz/ConvLSTM_pytorch)
* **Author:** Andrea Palazzi
* **License:** MIT License
* **Files:** `ConvAE/convlstm.py`
* **Local Modifications:**
  - In `ConvLSTMCell.init_hidden()`, replaced hardcoded `.cuda()` / `torch.cuda.current_device()` with `device=self.conv.weight.device`, ensuring device compatibility across CPU, CUDA, and Apple Silicon MPS.

---

## 3. Distributed and Grouped Batch Samplers

* **Source Repository:** [facebookresearch/maskrcnn-benchmark](https://github.com/facebookresearch/maskrcnn-benchmark)
* **Copyright:** Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
* **License:** BSD 3-Clause License
* **Files:** `ConvAE/utils/samplers/distributed.py`, `ConvAE/utils/samplers/grouped_batch_sampler.py`, `ConvAE/utils/samplers/iteration_based_batch_sampler.py`
* **Local Modifications:** Preserved original copyright headers; integrated with standard PyTorch `torch.utils.data.Sampler`.

---

## 4. DoTA Dataset Driving Videos

* **Source:** Public dashcam videos hosted on YouTube and research Google Drive mirrors provided by the DoTA authors.
* **Terms of Use:** Non-commercial research and academic evaluation only.
* **Storage Policy:** Videos and extracted raw frames are NEVER tracked in Git. They are fetched on demand via download manifests and stored under `data/` (which is `.gitignore`d).

---

## 5. Horn-Schunck Optical Flow

* **Origin:** Python adaptation of Horn & Schunck (1981), "Determining Optical Flow", *Artificial Intelligence*, 17:185–203.
* **Files:** `VIF/HornSchunck.py`
* **License:** Public Domain / BSD-compatible research implementation.
* **Local Modifications:**
  - Modernized `scipy.ndimage.filters` imports for SciPy 1.10+ / 2.0+ compatibility (`from scipy.ndimage import convolve, gaussian_filter`).
  - Added temporal boundary padding guard in `argus_ml/scoring/vif_svm.py` to prevent index errors when sequence lengths satisfy `len(frames) % 6 == 3`.

---

## 6. MOSSE Visual Object Tracker

* **Origin:** Visual Object Tracking using Minimum Output Sum of Squared Error (MOSSE) filters (Bolme et al., CVPR 2010).
* **Files:** `Mosse_Tracker/*`
* **License:** BSD 3-Clause License / Academic use.
* **Local Modifications:** Integrated into Argus zeroMQ tracking pipeline (`RunTracker.py`) with Track-Compensated Frame Interpolation (TCFI).

---

## 7. Haar Cascades & Pretrained Vehicle Weights

* **Source:** OpenCV open-source vehicle cascade models.
* **Files:** `Car_Detection/cars3.xml`, `Car_Detection/cars.xml`
* **License:** Apache License 2.0 / BSD 3-Clause.
* **Policy:** Preserved for legacy headless CV node support. Modern detectors interface via the pluggable detector stage in `backend/app/cv/detection.py`.

---

## 8. Support Vector Machine Model Exports

* **Source:** Original trained model `VIF/model-svm1.sav` generated with scikit-learn 0.22.2.
* **Export Artifacts:**
  - `artifacts/models/vif_svm.onnx` (Direct ONNX export with 100% mathematical parity and `probA_`/`probB_` Platt scaling attributes).
  - `artifacts/models/vif_svm_retrained.onnx` (Retrained on grouped CCTV train split with balanced class weighting).
* **License:** MIT License.


