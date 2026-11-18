import math
import os
import cv2

from Mosse_Tracker.TrackerManager import TrackerType
from System.Data.CONSTANTS import Work_Crash_Estimation_Only


class Crashing:

    def __init__(self, vif, config=None):
        self.vif = vif
        self.config = config or {}
        self.last_model_scores = None
        self.last_classifier_scores = []
        self.last_failed_box_size = 0
        self.last_failed_aspect_ratio = 0
        self._batch_counter = 0

    def crash(self, frames, trackers, camera_id=None, starting_frame_id=None, run_id=None, batch_index=None, config=None):
        cfg = config or self.config
        crash_dimentions = []
        self.last_classifier_scores = []
        self.last_failed_box_size = 0
        self.last_failed_aspect_ratio = 0

        trace_active = os.getenv("ARGUS_TRACE", "false").lower() in ("true", "1", "yes")
        pairs_evaluated = 0
        failed_speed = 0
        failed_distance = 0
        failed_deviation = 0
        candidates_passed_geometry = 0

        dist_factor = float(cfg.get("distance_factor", os.getenv("CRASH_DISTANCE_FACTOR", "0.25")))

        for i in range(len(trackers)):
            for j in range(i + 1, len(trackers)):
                if i == j:
                    continue
                tracker_A = trackers[i]
                tracker_B = trackers[j]
                pairs_evaluated += 1

                # calculate the distance
                asize = pow(pow(tracker_A.vehicle_height, 2) + pow(tracker_A.vehicle_width, 2), 0.5) * dist_factor
                bsize = pow(pow(tracker_B.vehicle_height, 2) + pow(tracker_B.vehicle_width, 2), 0.5) * dist_factor
                dis = asize + bsize

                speed_ok = False
                dist_ok = False
                any_passed = False

                for f_no in (16, 19, 22, 25, 28):
                    passed, reason = self._check_distance_detailed(tracker_A, tracker_B, f_no, dis)
                    if passed:
                        any_passed = True
                        break
                    if reason == "speed":
                        pass
                    elif reason == "distance":
                        speed_ok = True
                    elif reason == "deviation":
                        speed_ok = True
                        dist_ok = True

                if any_passed:
                    candidates_passed_geometry += 1
                    print("#################collision has occured!")
                    if Work_Crash_Estimation_Only:
                        self.crashEstimation(crash_dimentions, tracker_A, tracker_B, frames)
                    else:
                        crash_dimentions.extend(self.predict(frames, [tracker_B, tracker_A]))
                else:
                    if not speed_ok:
                        failed_speed += 1
                    elif not dist_ok:
                        failed_distance += 1
                    else:
                        failed_deviation += 1

        enable_single_vehicle = bool(cfg.get("single_vehicle_mode", os.getenv("CRASH_SINGLE_VEHICLE", "false").lower() in ("true", "1", "yes")))
        if enable_single_vehicle and len(trackers) == 1:
            pairs_evaluated += 1
            tracker_single = trackers[0]
            if self._check_single_vehicle_anomaly(tracker_single):
                candidates_passed_geometry += 1
                if Work_Crash_Estimation_Only:
                    pass
                else:
                    crash_dimentions.extend(self.predict(frames, [tracker_single]))
            else:
                failed_speed += 1

        if len(crash_dimentions) > 0:
            xmin = 10000
            ymin = 10000
            xmax = 0
            ymax = 0
            for crash_dimension in crash_dimentions:
                xmin = min(xmin, crash_dimension[0])
                ymin = min(ymin, crash_dimension[1])
                xmax = max(xmax, crash_dimension[2])
                ymax = max(ymax, crash_dimension[3])
            crash_dimentions = [xmin, ymin, xmax, ymax]
        else:
            crash_dimentions = []

        if trace_active:
            try:
                from argus_ml.trace import record_batch_trace
                target_run_id = run_id or os.getenv("ARGUS_TRACE_RUN_ID") or (str(camera_id) if camera_id is not None else "default")
                self._batch_counter += 1
                b_idx = batch_index if batch_index is not None else self._batch_counter

                max_score = max(self.last_classifier_scores) if self.last_classifier_scores else None
                decision = len(crash_dimentions) > 0

                is_degraded = (
                    os.getenv("ARGUS_DETECTION_QUALITY", "").lower() in ("motion_fallback", "unavailable")
                    or os.getenv("ARGUS_LOW_QUALITY", "false").lower() in ("true", "1")
                )

                if decision:
                    primary_reason = "CRASH_DETECTED"
                elif is_degraded:
                    primary_reason = "LOW_QUALITY_DETECTION"
                elif len(trackers) == 0:
                    primary_reason = "NO_DETECTIONS"
                elif len(trackers) == 1:
                    primary_reason = "SINGLE_VEHICLE"
                elif failed_distance == pairs_evaluated and pairs_evaluated > 0:
                    primary_reason = "TOO_FAR"
                elif failed_speed == pairs_evaluated and pairs_evaluated > 0:
                    primary_reason = "BELOW_SPEED"
                elif failed_deviation == pairs_evaluated and pairs_evaluated > 0:
                    primary_reason = "NO_DEVIATION"
                elif self.last_failed_box_size > 0:
                    primary_reason = "FILTERED_BOX_SIZE"
                elif self.last_failed_aspect_ratio > 0:
                    primary_reason = "FILTERED_ASPECT_RATIO"
                elif max_score is not None and max_score < 0.5:
                    primary_reason = "CLASSIFIER_LOW_SCORE"
                else:
                    primary_reason = "OTHER"

                trace_record = {
                    "run_id": target_run_id,
                    "batch_index": b_idx,
                    "starting_frame_id": starting_frame_id,
                    "num_detections": len(trackers),
                    "num_trackers": len(trackers),
                    "pairs_evaluated": pairs_evaluated,
                    "failed_speed": failed_speed,
                    "failed_distance": failed_distance,
                    "failed_deviation": failed_deviation,
                    "candidates_passed_geometry": candidates_passed_geometry,
                    "failed_box_size": self.last_failed_box_size,
                    "failed_aspect_ratio": self.last_failed_aspect_ratio,
                    "classifier_score": round(max_score, 4) if max_score is not None else None,
                    "decision": decision,
                    "primary_reason": primary_reason,
                }
                record_batch_trace(target_run_id, trace_record)
            except Exception:
                pass

        return crash_dimentions

    def _check_distance_detailed(self, tracker_A, tracker_B, frame_no, dis):
        if not tracker_A.isAboveSpeedLimit(frame_no - 10, frame_no) and not tracker_B.isAboveSpeedLimit(frame_no - 10, frame_no):
            return False, "speed"

        xa, ya = tracker_A.estimationFutureCenter[frame_no]
        xb, yb = tracker_B.estimationFutureCenter[frame_no]
        r = pow(pow(xa - xb, 2) + pow(ya - yb, 2), 0.5)

        if r == 0:
            return True, "passed"
        elif r > dis:
            return False, "distance"

        if tracker_A.tracker_type == TrackerType.MOSSE:
            xa_actual, ya_actual = tracker_A.tracker.centers[frame_no]
            xb_actual, yb_actual = tracker_B.tracker.centers[frame_no]
        else:
            xa_actual, ya_actual = tracker_A.get_position(tracker_A.history[frame_no])
            xb_actual, yb_actual = tracker_B.get_position(tracker_B.history[frame_no])
        difference_trackerA_actual_to_estimate = pow(pow(xa_actual - xa, 2) + pow(ya_actual - ya, 2), 0.5)
        difference_trackerB_actual_to_estimate = pow(pow(xb_actual - xb, 2) + pow(yb_actual - yb, 2), 0.5)
        max_difference = max(difference_trackerA_actual_to_estimate, difference_trackerB_actual_to_estimate)

        if max_difference / r > 0.5:
            return True, "passed"
        return False, "deviation"

    def checkDistance(self, tracker_A, tracker_B, frame_no, dis):
        passed, _ = self._check_distance_detailed(tracker_A, tracker_B, frame_no, dis)
        return passed

    def _get_tracker_center(self, tracker, frame_no: int):
        """Retrieve center coordinates (x, y) of a tracker at the specified frame."""
        try:
            if hasattr(tracker, "tracker") and hasattr(tracker.tracker, "centers") and len(tracker.tracker.centers) > frame_no:
                return tracker.tracker.centers[frame_no]
            if hasattr(tracker, "history") and len(tracker.history) > frame_no:
                box = tracker.history[frame_no]
                if isinstance(box, (list, tuple)) and len(box) >= 4:
                    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
                elif isinstance(box, (list, tuple)) and len(box) == 2:
                    return box
            if hasattr(tracker, "center"):
                return tracker.center
        except Exception:
            pass
        return None

    def _check_single_vehicle_anomaly(self, tracker) -> bool:
        """
        Evaluate a single tracker for single-vehicle crash anomalies.
        Active when CRASH_SINGLE_VEHICLE=true.

        Anomaly triggers:
          1. Abrupt Deceleration:
             Speed in early window (frames 0-10) > 30 and drops by >= CRASH_SINGLE_DECEL_THRESHOLD (default 0.60 = 60%).
          2. Heading Change / Sudden Swerve:
             Angle between early motion vector (frames 0 to 10) and late motion vector (frames 15 to 28)
             exceeds CRASH_SINGLE_HEADING_ANGLE (default 45.0 degrees).

        NOTE: Enabling single-vehicle crash analysis allows detection of single-car impacts
        (guardrails, utility poles, spinouts, rollover), but can introduce false alarms from
        emergency braking or sharp turning at intersections.
        """
        try:
            # 1. Abrupt deceleration check
            decel_ratio = float(os.getenv("CRASH_SINGLE_DECEL_THRESHOLD", "0.60"))
            s_start = tracker.getAvgSpeed(0, 10)
            s_end = tracker.getAvgSpeed(15, 28)
            if s_start is not None and s_end is not None and s_start > 30:
                if s_end < s_start * (1.0 - decel_ratio):
                    return True

            # 2. Heading change / swerve check
            heading_thresh = float(os.getenv("CRASH_SINGLE_HEADING_ANGLE", "45.0"))
            c0 = self._get_tracker_center(tracker, 0)
            c10 = self._get_tracker_center(tracker, 10)
            c15 = self._get_tracker_center(tracker, 15)
            c28 = self._get_tracker_center(tracker, 28)

            if c0 is not None and c10 is not None and c15 is not None and c28 is not None:
                v1 = (c10[0] - c0[0], c10[1] - c0[1])
                v2 = (c28[0] - c15[0], c28[1] - c15[1])
                mag1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
                mag2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5
                # Require minimum displacement in both segments (at least 5 pixels)
                if mag1 >= 5.0 and mag2 >= 5.0:
                    dot = v1[0] * v2[0] + v1[1] * v2[1]
                    cos_theta = max(-1.0, min(1.0, dot / (mag1 * mag2)))
                    angle_deg = math.degrees(math.acos(cos_theta))
                    if angle_deg >= heading_thresh:
                        return True

            return False
        except Exception:
            return False

    def predict(self,frames_RGB, trackers):
        gray_frames = self.convertToGrayFrames(frames_RGB)
        no_crash = 0
        crash = 0

        enable_ensemble = os.environ.get("ARGUS_ENABLE_ENSEMBLE", "false").lower() in ("true", "1", "yes")
        ensemble = None
        if enable_ensemble:
            try:
                from argus_ml.scoring.ensemble import CrashEnsemble
                from argus_ml.scoring.vif_svm import VifSvmScorer
                from argus_ml.scoring.convae import ConvAEScorer
                from argus_ml.scoring.onnx_classifier import OnnxClassifierScorer

                policy = os.environ.get("CRASH_POLICY", os.environ.get("ARGUS_ENSEMBLE_POLICY", "majority"))
                ensemble = CrashEnsemble(
                    scorers=[VifSvmScorer(), ConvAEScorer(), OnnxClassifierScorer()],
                    policy=policy,
                )
            except Exception:
                enable_ensemble = False

        crash_dimentions = []
        for tracker in trackers:
            tracker_frames, width, height, xmin, xmax, ymin, ymax = tracker.getFramesOfTracking(gray_frames)
            crash_dimentions.append([xmin,ymin,xmax,ymax])

            if tracker_frames == None:
                continue

            adaptive_box = bool(self.config.get("adaptive_box_filter", os.getenv("CRASH_ADAPTIVE_BOX_FILTER", "false").lower() in ("true", "1", "yes")))
            if adaptive_box:
                frame_h, frame_w = gray_frames[0].shape[:2] if gray_frames and len(gray_frames) > 0 else (360, 480)
                frac = float(os.getenv("CRASH_ADAPTIVE_BOX_FRACTION", "0.04"))
                min_w = max(15, int(frame_w * frac))
                min_h = max(10, int(frame_h * frac))
                min_aspect = float(os.getenv("CRASH_MIN_ASPECT_RATIO", "0.20"))
            else:
                min_w = 50
                min_h = 28
                min_aspect = 0.35

            if xmax - xmin < min_w:  # 50
                self.last_failed_box_size += 1
                continue
            if ymax - ymin <= min_h:  # 28
                self.last_failed_box_size += 1
                continue

            if (ymax - ymin) / (xmax - xmin) < min_aspect:  # 0.35
                self.last_failed_aspect_ratio += 1
                continue

            clf_thresh = float(os.getenv("CRASH_CLASSIFIER_THRESHOLD", "0.50"))

            if enable_ensemble and ensemble is not None:
                from argus_ml.scoring.base import ClipInput
                clip = ClipInput(frames=tracker_frames)
                scores_payload, decision, _ = ensemble.evaluate(clip)
                self.last_model_scores = scores_payload.model_dump()
                active_scores = [s.score for s in scores_payload.scorers if getattr(s, "available", False) and s.score is not None]
                ens_score = float(max(active_scores)) if active_scores else (1.0 if decision else 0.0)
                self.last_classifier_scores.append(ens_score)
                if not decision:
                    no_crash += 1
                else:
                    crash += 1
                    tracker.saveTracking(frames_RGB)
            else:
                feature_vec = self.vif.process(tracker_frames)
                score = 0.0
                if hasattr(self.vif.clf, "predict_proba"):
                    try:
                        score = float(self.vif.clf.predict_proba(feature_vec.reshape(1, 304))[0][1])
                    except Exception:
                        score = 0.0
                self.last_classifier_scores.append(score)

                if clf_thresh != 0.50 and hasattr(self.vif.clf, "predict_proba"):
                    is_crash = (score >= clf_thresh)
                else:
                    result = self.vif.clf.predict(feature_vec.reshape(1, 304))
                    is_crash = (result[0] != 0.0)

                if not is_crash:
                    no_crash += 1
                else:
                    crash += 1
                    tracker.saveTracking(frames_RGB)

        if crash == 0:
            crash_dimentions = []
        # print(crash, no_crash)
        return crash_dimentions




    def convertToGrayFrames(self,frames_RGB):
        gray_frames = []
        for frame in frames_RGB:
            gray_frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        return gray_frames


    def crashEstimation(self, crash_dimentions, tracker_A, tracker_B, frames):
        gray_frames = self.convertToGrayFrames(frames)
        adaptive_box = bool(self.config.get("adaptive_box_filter", os.getenv("CRASH_ADAPTIVE_BOX_FILTER", "false").lower() in ("true", "1", "yes")))
        if adaptive_box:
            frame_h, frame_w = gray_frames[0].shape[:2] if gray_frames and len(gray_frames) > 0 else (360, 480)
            frac = float(os.getenv("CRASH_ADAPTIVE_BOX_FRACTION", "0.04"))
            min_w = max(15, int(frame_w * frac))
            min_h = max(10, int(frame_h * frac))
            min_aspect = float(os.getenv("CRASH_MIN_ASPECT_RATIO", "0.20"))
        else:
            min_w = 50
            min_h = 28
            min_aspect = 0.35

        for trk in (tracker_A, tracker_B):
            tracker_frames, width, height, xmin, xmax, ymin, ymax = trk.getFramesOfTracking(gray_frames)
            bw = xmax - xmin
            bh = ymax - ymin
            if bw < min_w or bh <= min_h or (bh / bw) < min_aspect:
                pass
            else:
                crash_dimentions.extend([[xmin, ymin, xmax, ymax]])
