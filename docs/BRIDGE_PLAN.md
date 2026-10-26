# Argus Bridge Architecture & Integration Plan (`docs/BRIDGE_PLAN.md`)

## 1. ZeroMQ Socket Architecture

The Argus system communicates across microservices using **ZeroMQ (pyzmq)**. 
A critical finding is that **all Argus message transfers use Python object pickling (`socket.send_pyobj` / `socket.recv_pyobj`)**, not raw JSON byte strings.

All socket endpoints, bindings, patterns, and message schemas are documented below:

| Port | Service Node | Pattern | Who Binds | Who Connects | Serialization | Message Types Handled |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`10000`** | **Master** (`RunMaster.py`) | **REQ / REP** | Master (`ReceiverController`) binds `tcp://*:10000` | `CameraNode`, `Crash Node`, `RunGui.py` (or Bridge) connect | `pyobj` (pickle) | `FEED`, `RESULT`, `SEARCH`, `RECENT_CRASHES`, `REQ_VIDEO` |
| **`10002`** | **Detection** (`RunDetect.py`) | **REQ / REP** | Detect (`ReceiverController`) binds `tcp://*:10002` | Master (`JsonEncoder`) connects | `pyobj` (pickle) | `DETECT` |
| **`10004`** | **Tracking** (`RunTracker.py`) | **REQ / REP** | Tracker (`ReceiverController`) binds `tcp://*:10004` | Detection (`JsonEncoder`) connects | `pyobj` (pickle) | `TRACK` |
| **`10008`** | **Crash** (`RunCrash.py`) | **REQ / REP** | Crash (`ReceiverController`) binds `tcp://*:10008` | Tracker (`JsonEncoder`) connects | `pyobj` (pickle) | `CRASH` |
| **`10010`** | **GUI / Surveillance** (`RunGui.py`) | **REQ / REP** | GUI (`WorkerThread`) binds `tcp://127.0.0.1:10010` | Master (`JsonEncoder`) connects | `pyobj` (pickle) | `NOTIFICATION`, `REP_QUERY`, `REP_VIDEO` |

---

### Detailed Socket Message Schemas

#### A. Port `10010`: Surveillance Alert & Master-to-GUI Socket (Bound by GUI/Bridge)

1. **`NOTIFICATION`** (Real-time Crash Alert sent by Master to GUI):
   ```python
   {
       "FUNCTION": "NOTIFICATION",
       "CAMERA_ID": int,            # e.g., 1528
       "STARTING_FRAME_ID": int,    # Starting frame ID of incident sequence (e.g., 76)
       "CITY": str,                 # e.g., "Cairo"
       "DISTRICT": str,             # e.g., "District 13"
       "CRASH_TIME": str,           # Format: "YYYY-MM-DD HH:MM:SS" (UTC)
       "CRASH_PIC": numpy.ndarray   # OpenCV BGR image array (uint8) of the collision frame
   }
   ```
   *Response expected by Master:* `""` (empty string via `socket.send_pyobj("")`).

2. **`REP_QUERY`** (Historical Query Reply sent by Master):
   ```python
   {
       "FUNCTION": "REP_QUERY",
       "LIST_OF_CRASHES": [
           {
               "CAMERA_ID": int,
               "STARTING_FRAME_ID": int,
               "CITY": str,
               "DISTRICT": str,
               "CRASH_TIME": str,
               "CRASH_PIC": numpy.ndarray  # OpenCV BGR image array or None
           },
           ...
       ]
   }
   ```
   *Response expected by Master:* `""` (empty string).

3. **`REP_VIDEO`** (Video Replay Reply sent by Master):
   ```python
   {
       "FUNCTION": "REP_VIDEO",
       "FRAMES": [numpy.ndarray, ...] # List of BGR numpy frame arrays
   }
   ```
   *Response expected by Master:* `""` (empty string).

---

#### B. Port `10000`: Master Node Control Socket (Bound by Master)

1. **`FEED`** (Sent by `CameraNode` to stream raw frames):
   ```python
   {
       "FUNCTION": "FEED",
       "CAMERA_ID": int,
       "STARTING_FRAME_ID": int,
       "FRAMES": [numpy.ndarray, ...], # 30 frames
       "FRAME_WIDTH": int,             # 480
       "FRAME_HEIGHT": int,            # 360
       "READ_FILE": bool,              # True if reading pre-extracted boxes
       "BOXES": list,                  # Bounding boxes for first frame
       "CITY": str,
       "DISTRICT": str
   }
   ```

2. **`SEARCH`** (Sent by Client to filter historical crashes):
   ```python
   {
       "FUNCTION": "SEARCH",
       "START_DATE": str,   # "DD/MM/YYYY"
       "END_DATE": str,     # "DD/MM/YYYY"
       "START_TIME": str,   # "HH:MM"
       "END_TIME": str,     # "HH:MM"
       "CITY": str | None,
       "DISTRICT": str | None
   }
   ```

3. **`RECENT_CRASHES`** (Sent by Client to fetch newest 10 crashes):
   ```python
   {
       "FUNCTION": "RECENT_CRASHES"
   }
   ```

4. **`REQ_VIDEO`** (Sent by Client to request stitched incident footage):
   ```python
   {
       "FUNCTION": "REQ_VIDEO",
       "CAMERA_ID": int,
       "STARTING_FRAME_ID": int
   }
   ```

---

## 2. Incident Storage, Thumbnails & Video Clips

### Database
* **File Location**: `System/Database/Argus_DB.db` (SQLite 3).
* **Primary Table**: `CrashFrames`
  * `camera_id` (INTEGER): Identifier of camera / video source.
  * `frame_id` (INTEGER): Starting frame index of collision sequence.
  * `from_no` (INTEGER): Number of 30-frame chunks stitched so far ($5 = 150$ frames total).
  * `city` (TEXT): Municipal locality name.
  * `district` (TEXT): Sub-district designation.
  * `crash_time` (TEXT): Timestamp in `"YYYY-MM-DD HH:MM:SS"`.
  * Implicit `rowid` (INTEGER): Unique SQLite row identifier.
* **Secondary Table**: `SavedFrames`
  * `camera_id` (INTEGER)
  * `frame_id` (INTEGER)

### Video Clips
* **Raw Video Chunks**: `./saved_frames_vid/({camera_id}) {frame_id}.avi`
* **Stitched Crash Video Clips**: `./saved_crash_vid/({camera_id}) {frame_id}.avi`
  * Codec: Motion JPEG (`MJPG`), container: `AVI`, frame rate: `30 FPS`.
  * Resolution: `480x360` pixels.
  * Duration: Up to 150 frames (5 seconds: 60 pre-crash, 30 crash highlight with red box + text, 60 post-crash).

### Thumbnails
* Argus does **not** persist individual thumbnail image files on disk during native operation.
* Instead, `Master.getCrashPhoto(camera_id, starting_frame_id)` opens `./saved_crash_vid/({camera_id}) {starting_frame_id}.avi`, reads frame 89 (or the last frame), and ships the BGR numpy array over ZeroMQ in `CRASH_PIC`.
* **Bridge Strategy**: The FastAPI backend intercepts `CRASH_PIC` upon arrival, serializes it as JPEG to `backend/media/thumbnails/{incident_id}.jpg`, and caches it. If an older incident from SQLite does not have a cached JPEG, the bridge generates it on-demand from `./saved_crash_vid/({camera_id}) {frame_id}.avi`, falling back to `UI/notfound.png` if the clip is unavailable.

---

## 3. CameraNode & Video Streaming Execution

When **"Process"** is clicked in `RunCamera.py`:
1. **Inputs required**:
   * `file_path`: Absolute or relative path to video (e.g., `videos/1528.mp4`).
   * `camera_id`: Integer extracted from filename or randomly assigned.
   * `city`: City name selected from random Egyptian city list or configured.
   * `district`: District string (e.g., `"District 13"`).
   * `files`: Boolean (`Work_Detect_Files` from `CONSTANTS.py`), determines whether to read YOLO boxes from `boxes/{camera_id}.txt` or run live YOLO.
2. **Streaming Execution**:
   * Initializes `CameraNode(camera_id, file_path, files, city, district_no)`.
   * Resizes frames to $480 \times 360$ resolution (`cv2.INTER_AREA`).
   * Accumulates rolling 30-frame buffers with 15-frame overlap (stepping by 15 frames).
   * Bundles the 30 frames with the initial frame bounding boxes and sends a `FEED` message via `zmq.REQ` to Master on port 10000.
   * Master saves raw chunks, triggers `RunDetect.py`, tracks through `RunTracker.py`, and evaluates via `RunCrash.py`.

---

## 4. Python Environment & Fragile Dependencies

| Dependency | Required Version | Fragility & Risk Analysis |
| :--- | :--- | :--- |
| **Python** | `3.11` | **High Fragility in 3.12+**: Python 3.13/3.14 removed standard library `imghdr` used by `Car_Detection/visualize.py`. Pre-built wheels for PyQt5 are also unavailable on 3.14 macOS arm64. |
| **PyQt5** | `5.15.x` | Desktop GUI requirement only; replaced entirely by React + FastAPI bridge. |
| **dlib** | `19.x` | Extremely fragile (requires CMake + C++ compiler). Argus avoids it when `Work_Tracker_Type_Mosse = True` (pure NumPy/OpenCV MOSSE tracker). |
| **scikit-learn** | `0.22.x` $\rightarrow$ `1.x` | `model-svm1.sav` was serialized with sklearn 0.22.2. Loading in sklearn 1.x emits `InconsistentVersionWarning` but works. |
| **OpenCV** | `opencv-python 4.x / 5.x` | High stability. Used for frame manipulation and AVI generation. |
| **ZeroMQ (`pyzmq`)** | `25.x+` | Uses Python `pickle` protocol. High security risk if opened to untrusted networks without authentication. Must be bound to localhost (`127.0.0.1`). |
| **ffmpeg** | System binary | Required on host for transcoding raw AVI (`MJPG`) to browser-compatible MP4 (`H.264 / yuv420p / faststart`). |

---

## 5. Feature Mapping: Qt Apps to REST / WebSocket & React

| Qt Application | UI Widget / Action | Argus Mechanism | Bridge REST / WebSocket Endpoint | React Component |
| :--- | :--- | :--- | :--- | :--- |
| `RunGui.py` | Real-time Incident Alert Card | ZMQ REP `10010` `NOTIFICATION` | `WebSocket /ws/alerts` | `<IncidentAlertBanner />` & `<IncidentCard />` |
| `RunGui.py` | Alarm Audio (`siren.mp3`) | `pygame.mixer.music.play()` | Browser Web Audio API / `<audio>` trigger on alert | `<AlertAudioPlayer />` |
| `RunGui.py` | "Recent" Button | ZMQ `RECENT_CRASHES` $\rightarrow$ SQLite query | `GET /api/incidents/recent` | `<RecentIncidentsList />` |
| `RunGui.py` | Search Filter (Date/Time/City/Loc) | ZMQ `SEARCH` $\rightarrow$ SQLite query | `GET /api/incidents?start_date=...` | `<IncidentFilterForm />` |
| `RunGui.py` | Incident Thumbnail in List | Extracted BGR frame in memory | `GET /media/thumbnails/{id}.jpg` | `<IncidentThumbnail />` |
| `RunGui.py` | Double-click Incident $\rightarrow$ Play Video | ZMQ `REQ_VIDEO` $\rightarrow$ OpenCV `cv2.imshow` | `GET /api/incidents/{id}/video` (MP4 H.264 Range) | `<IncidentVideoModal />` (`<video>`) |
| `RunCamera.py`| Video Selector & Drag-and-Drop | `QFileDialog.getOpenFileName` | `GET /api/videos` & `POST /api/cameras/upload` | `<VideoUploadDropzone />` |
| `RunCamera.py`| "Process" Button | Starts `CameraNode` thread | `POST /api/cameras/simulate` | `<CameraSimulatePanel />` |
| `RunCamera.py`| Video Playback Preview | Local OpenCV loop | `GET /api/videos/{video_id}/stream` | `<VideoPreviewPlayer />` |
| Both Apps | System Health & Node Status | Implicit (sockets assume running) | `GET /api/health` | `<SystemHealthBadge />` |

---

## 6. Blockers, Limitations & Minimal Non-Modifying Workarounds

1. **Single-Listener Constraint on Port `10010` (REQ/REP Pattern)**:
   * *Problem*: Argus uses `zmq.REP` on port 10010 instead of `PUB/SUB`. Only a single process can bind to `127.0.0.1:10010`. If `RunGui.py` is open, no other service can listen for alerts on 10010.
   * *Zero-Argus-Modification Solution*: The FastAPI bridge acts as the modern drop-in replacement for `RunGui.py` and binds to port 10010. The bridge's background thread receives the alerts, responds with `""`, and fans out via WebSocket to unlimited connected browser clients.
2. **Browser Video Playback of `MJPG AVI`**:
   * *Problem*: HTML5 `<video>` tags do not natively support Motion JPEG in AVI containers.
   * *Zero-Argus-Modification Solution*: The bridge dynamically transcodes requested AVI clips to `H.264 MP4` (`yuv420p` with `-movflags +faststart`) using background `ffmpeg`, caches the result, and serves it with HTTP 206 Partial Content range support.
3. **Thumbnail Generation on Demand**:
   * *Problem*: Argus generates thumbnails on the fly as NumPy arrays in RAM and does not write `.jpg` files to disk.
   * *Zero-Argus-Modification Solution*: The bridge persists the received array as a JPEG into `backend/media/thumbnails/{id}.jpg` whenever an alert is received, and reads the AVI frame dynamically when querying historical database entries, using `UI/notfound.png` as fallback.
