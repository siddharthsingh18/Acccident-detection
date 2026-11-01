# ConvAE & DoTA Local Patches & Modifications

This document records all modifications made to the imported upstream [DoTA](https://github.com/MoonBlvd/Detection-of-Traffic-Anomaly) code to ensure portability, stability, multi-platform device support (CPU, CUDA, Apple Silicon MPS), and repository hygiene.

---

### Patch 1: Dynamic Device Support in `ConvLSTMCell` (`ConvAE/convlstm.py`)
- **Before:**
  ```python
  def init_hidden(self, batch_size):
      cur_device = torch.cuda.current_device()
      return (Variable(torch.zeros(batch_size, self.hidden_dim, self.height, self.width)).cuda(cur_device),
              Variable(torch.zeros(batch_size, self.hidden_dim, self.height, self.width)).cuda(cur_device))
  ```
- **After:**
  ```python
  def init_hidden(self, batch_size):
      device = self.conv.weight.device
      return (
          Variable(torch.zeros(batch_size, self.hidden_dim, self.height, self.width, device=device)),
          Variable(torch.zeros(batch_size, self.hidden_dim, self.height, self.width, device=device)),
      )
  ```
- **Reasoning:** Calling `.cuda()` crashes immediately on systems without NVIDIA GPUs (such as macOS Apple Silicon or standard CPU containers). Querying `self.conv.weight.device` ensures the hidden state is automatically placed on whichever device the model weights reside on (CPU, CUDA, or MPS).

---

### Patch 2: Dynamic Device Detection in `test.py` and `train.py`
- **Before:**
  ```python
  device = 'cuda'
  ```
- **After:**
  ```python
  device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
  ```
- **Reasoning:** Allows running evaluation and validation passes on Apple Silicon Macs or standard CPU systems without hard crashes.

---

### Patch 3: Removal of Author-Specific Hardcoded Paths
- **Before:**
  ```python
  # ConvAE/a3d.py, test.py, train.py
  sys.path.append('/home/brianyao/Documents/stad-cvpr2020')
  root = '/mnt/workspace/datasets/A3D_2.0/'
  flo_root = os.path.join('/mnt/workspace/datasets/A3D_2.0', 'flownet2/')
  ```
- **After:**
  ```python
  ROOT_DEFAULT = os.environ.get("DOTA_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "DoTA"))
  root = ROOT_DEFAULT
  flo_root = flow_root or os.environ.get("DOTA_FLOW_DIR", os.path.join(root, 'flownet2/'))
  ```
- **Reasoning:** Upstream files referenced directories on the original author's research server. Now defaults to project-relative `data/DoTA` or configurable environment variables `DOTA_DATA_DIR` and `DOTA_FLOW_DIR`.

---

### Patch 4: Optional Dependencies with Graceful Fallbacks (`ConvAE/train.py`)
- **Before:**
  ```python
  from mpi4py import MPI
  import apex
  from apex.parallel import DistributedDataParallel as DDP
  from detection.utils.logger import Logger
  from detection.utils.metric_logger import MetricLogger
  from detection.utils.comm import get_world_size, is_main_process, all_gather, synchronize
  ```
- **After:**
  ```python
  try:
      from mpi4py import MPI
  except ImportError:
      MPI = None

  try:
      import apex
      from apex.parallel import DistributedDataParallel as DDP
  except ImportError:
      apex = None
      DDP = None

  try:
      from detection.utils.comm import get_world_size, is_main_process, all_gather, synchronize
  except ImportError:
      def get_world_size(): return 1
      def is_main_process(): return True
      def all_gather(data): return [data]
      def synchronize(): pass
  ```
- **Reasoning:** `apex` and `mpi4py` are hardware-specific multi-GPU libraries not present in standard Python virtual environments. Wrapping them in try/except blocks allows training scripts to import and execute single-process routines on standard developer workstations.

---

### Patch 5: Removal of Interactive Breakpoints (`pdb.set_trace()`)
- **Before:**
  `pdb.set_trace()` calls existed in `ConvAE/conv2d_ae.py` (line 39), `ConvAE/train.py` (lines 298, 308), and unused `import pdb` in multiple files.
- **After:**
  All `pdb.set_trace()` calls and unused `pdb` imports removed.
- **Reasoning:** `pdb.set_trace()` freezes automated headless pipelines, web requests, and CI test runners waiting indefinitely for stdin input.

---

### Patch 6: Spatial Dimension Requirements for `ConvLSTMED`
- **Specification:**
  In `ConvAE/convlstm_ae.py`, `ConvEncoder` performs spatial downsampling using kernels/strides that map an input of size `(Batch, Channels, 227, 227)` to `(Batch, Channels, 26, 26)`. The subsequent `ConvLSTMDecoder` expects this exact spatial feature map to invert cleanly.
- **Integration Note:** Video preprocessing for ConvAE must resize frames to `227x227` pixels prior to passing into the model.
