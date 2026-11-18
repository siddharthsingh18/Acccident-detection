#!/usr/bin/env python3
"""
scripts/eval_detector.py

Argus Vehicle Detector Evaluation & Benchmarking Script.
Evaluates detection performance on held-out CCTV frames against COCO ground truth at IoU 0.50.
Computes:
  - Precision, Recall, F1, and AP@0.5 for vehicle classes (car, truck, bus, motorcycle)
  - Breakdown by environmental condition (day, night, rain)
  - Breakdown by object size bucket (small: <32^2, medium: 32^2-96^2, large: >96^2)
  - Inference throughput (FPS) and latency (ms/frame) on current hardware
  - Bootstrap 95% Confidence Intervals (CI) over clip groups to prevent pseudo-replication
"""
import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from System.Functions.Detector.yolo import ModernYoloDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval_detector")

DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "detection_eval" / "manifest.csv"
DEFAULT_COCO = PROJECT_ROOT / "data" / "detection_eval" / "coco_annotations.json"


def compute_iou(boxA: List[float], boxB: List[float]) -> float:
    """Compute IoU between two [x, y, w, h] boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

    interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
    boxAArea = boxA[2] * boxA[3]
    boxBArea = boxB[2] * boxB[3]

    unionArea = boxAArea + boxBArea - interArea
    if unionArea <= 0:
        return 0.0
    return interArea / unionArea


def get_size_bucket(area: float) -> str:
    """COCO standard area buckets."""
    if area < 32 * 32:
        return "small"
    elif area <= 96 * 96:
        return "medium"
    else:
        return "large"


def match_detections_for_image(
    pred_boxes: List[Dict],
    gt_boxes: List[Dict],
    iou_thresh: float = 0.50
) -> Tuple[List[Dict], int]:
    """
    Match predictions to ground truth bounding boxes greedy by confidence.
    Returns:
      matched_preds: list of pred dicts with keys 'tp' (1 or 0), 'score', 'size', etc.
      num_gt: total ground-truth count for this image
    """
    # Sort predictions by score descending
    sorted_preds = sorted(pred_boxes, key=lambda p: p["score"], reverse=True)
    gt_matched = [False] * len(gt_boxes)

    matched_preds = []
    for pred in sorted_preds:
        best_iou = 0.0
        best_gt_idx = -1
        p_bbox = pred["bbox"]

        for idx, gt in enumerate(gt_boxes):
            if gt_matched[idx]:
                continue
            iou = compute_iou(p_bbox, gt["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = idx

        size_bucket = get_size_bucket(p_bbox[2] * p_bbox[3])
        if best_iou >= iou_thresh and best_gt_idx >= 0:
            gt_matched[best_gt_idx] = True
            matched_preds.append({
                "tp": 1,
                "score": pred["score"],
                "size": size_bucket,
                "cat": pred.get("category_name", "car"),
            })
        else:
            matched_preds.append({
                "tp": 0,
                "score": pred["score"],
                "size": size_bucket,
                "cat": pred.get("category_name", "car"),
            })

    return matched_preds, len(gt_boxes)


def calculate_metrics_from_matches(pred_records: List[Dict], total_gt: int) -> Dict[str, float]:
    """Calculate Precision, Recall, F1, and AP from scored predictions."""
    if total_gt == 0 and len(pred_records) == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "ap": 1.0, "tp": 0, "fp": 0, "fn": 0, "gt": 0}
    if total_gt == 0:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0, "ap": 0.0, "tp": 0, "fp": len(pred_records), "fn": 0, "gt": 0}

    # Sort all predictions globally by score descending
    sorted_records = sorted(pred_records, key=lambda x: x["score"], reverse=True)
    tps = np.array([r["tp"] for r in sorted_records])
    fps = 1 - tps

    tp_cum = np.cumsum(tps)
    fp_cum = np.cumsum(fps)

    recalls = tp_cum / float(total_gt)
    precisions = tp_cum / np.maximum(tp_cum + fp_cum, np.finfo(np.float64).eps)

    total_tp = int(tp_cum[-1]) if len(tp_cum) > 0 else 0
    total_fp = int(fp_cum[-1]) if len(fp_cum) > 0 else 0
    total_fn = total_gt - total_tp

    p = total_tp / max(1, total_tp + total_fp)
    r = total_tp / max(1, total_gt)
    f1 = 2 * (p * r) / max(1e-6, p + r)

    # 11-point AP calculation
    ap = 0.0
    for t in np.linspace(0.0, 1.0, 11):
        prec_at_rec = precisions[recalls >= t]
        if len(prec_at_rec) > 0:
            ap += np.max(prec_at_rec) / 11.0

    return {
        "precision": round(float(p), 4),
        "recall": round(float(r), 4),
        "f1": round(float(f1), 4),
        "ap": round(float(ap), 4),
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "gt": total_gt,
    }


def run_evaluation(
    split: str = "validation",
    detector_conf: float = 0.35,
    detector_stride: int = 1,
    iou_thresh: float = 0.50,
    bootstrap_iterations: int = 1000,
    manifest_path: Path = DEFAULT_MANIFEST,
    coco_path: Path = DEFAULT_COCO,
) -> Dict:
    if not manifest_path.exists() or not coco_path.exists():
        raise FileNotFoundError("Missing evaluation dataset files. Run scripts/data/extract_detection_eval_frames.py.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_rows = list(csv.DictReader(f))

    with open(coco_path, "r", encoding="utf-8") as f:
        coco_data = json.load(f)

    # Filter to requested split
    if split in ("validation", "val"):
        selected_split = "validation"
    elif split == "test":
        selected_split = "test"
    else:
        selected_split = "all"

    if selected_split != "all":
        valid_frames = {r["frame_path"] for r in manifest_rows if r["split"] == selected_split}
        eval_images = [img for img in coco_data["images"] if img["split"] == selected_split]
    else:
        valid_frames = {r["frame_path"] for r in manifest_rows}
        eval_images = coco_data["images"]

    img_meta_map = {img["id"]: img for img in eval_images}
    gt_by_image = {img["id"]: [] for img in eval_images}

    for ann in coco_data["annotations"]:
        if ann["image_id"] in img_meta_map:
            gt_by_image[ann["image_id"]].append(ann)

    # Initialize detector
    detector = ModernYoloDetector(
        confidence_threshold=detector_conf,
        frame_stride=detector_stride
    )

    logger.info(f"Evaluating {detector.name} (backend={detector.backend}, conf={detector_conf}) on '{selected_split}' split ({len(eval_images)} frames)...")

    # Run inference and measure latency
    total_time = 0.0
    group_results: Dict[str, Dict] = {}  # group_id -> list of preds, gt_count, conditions, sizes

    for img in eval_images:
        frame_file = PROJECT_ROOT / "data" / "detection_eval" / img["file_name"]
        group_id = img["clip_group_id"]
        condition = img["condition"]

        if group_id not in group_results:
            group_results[group_id] = {
                "preds": [],
                "gt_total": 0,
                "conditions": {
                    "day": {"preds": [], "gt": 0},
                    "night": {"preds": [], "gt": 0},
                    "rain": {"preds": [], "gt": 0},
                },
                "sizes": {
                    "small": {"preds": [], "gt": 0},
                    "medium": {"preds": [], "gt": 0},
                    "large": {"preds": [], "gt": 0},
                }
            }

        frame = cv2.imread(str(frame_file))
        if frame is None:
            continue

        h, w = frame.shape[:2]
        t0 = time.perf_counter()
        raw_boxes = detector.detect(frame)
        dt = time.perf_counter() - t0
        total_time += dt

        pred_boxes = []
        for b in raw_boxes:
            if len(b) >= 6:
                cat, x1, x2, y1, y2, sc = b[0], float(b[1]), float(b[2]), float(b[3]), float(b[4]), float(b[5])
                bw = max(0.0, x2 - x1)
                bh = max(0.0, y2 - y1)
                pred_boxes.append({
                    "bbox": [x1, y1, bw, bh],
                    "score": sc,
                    "category_name": str(cat).lower()
                })

        gt_boxes = gt_by_image.get(img["id"], [])
        matches, gt_count = match_detections_for_image(pred_boxes, gt_boxes, iou_thresh=iou_thresh)

        group_results[group_id]["preds"].extend(matches)
        group_results[group_id]["gt_total"] += gt_count

        # Stratified condition recording
        cond_key = condition if condition in ("day", "night", "rain") else "day"
        group_results[group_id]["conditions"][cond_key]["preds"].extend(matches)
        group_results[group_id]["conditions"][cond_key]["gt"] += gt_count

        # Stratified size recording
        for m in matches:
            sz = m.get("size", "medium")
            group_results[group_id]["sizes"][sz]["preds"].append(m)
        for gt in gt_boxes:
            gt_area = gt["bbox"][2] * gt["bbox"][3]
            gt_sz = get_size_bucket(gt_area)
            group_results[group_id]["sizes"][gt_sz]["gt"] += 1

    # Aggregate global metrics
    all_preds = []
    all_gt = 0
    cond_agg = {"day": {"preds": [], "gt": 0}, "night": {"preds": [], "gt": 0}, "rain": {"preds": [], "gt": 0}}
    size_agg = {"small": {"preds": [], "gt": 0}, "medium": {"preds": [], "gt": 0}, "large": {"preds": [], "gt": 0}}

    for g_id, g_data in group_results.items():
        all_preds.extend(g_data["preds"])
        all_gt += g_data["gt_total"]
        for c in ("day", "night", "rain"):
            cond_agg[c]["preds"].extend(g_data["conditions"][c]["preds"])
            cond_agg[c]["gt"] += g_data["conditions"][c]["gt"]
        for s in ("small", "medium", "large"):
            size_agg[s]["preds"].extend(g_data["sizes"][s]["preds"])
            size_agg[s]["gt"] += g_data["sizes"][s]["gt"]

    overall = calculate_metrics_from_matches(all_preds, all_gt)

    fps = round(len(eval_images) / max(1e-6, total_time), 1)
    latency_ms = round((total_time / max(1, len(eval_images))) * 1000.0, 2)

    # Condition breakdown
    cond_metrics = {c: calculate_metrics_from_matches(cond_agg[c]["preds"], cond_agg[c]["gt"]) for c in cond_agg}

    # Size breakdown
    size_metrics = {s: calculate_metrics_from_matches(size_agg[s]["preds"], size_agg[s]["gt"]) for s in size_agg}

    # Bootstrap 95% Confidence Intervals across clip groups
    groups = list(group_results.keys())
    rng = np.random.RandomState(42)
    b_f1 = []
    b_ap = []
    b_prec = []
    b_rec = []

    if len(groups) > 1 and bootstrap_iterations > 0:
        for _ in range(bootstrap_iterations):
            sampled_g = rng.choice(groups, size=len(groups), replace=True)
            boot_preds = []
            boot_gt = 0
            for sg in sampled_g:
                boot_preds.extend(group_results[sg]["preds"])
                boot_gt += group_results[sg]["gt_total"]
            bm = calculate_metrics_from_matches(boot_preds, boot_gt)
            b_f1.append(bm["f1"])
            b_ap.append(bm["ap"])
            b_prec.append(bm["precision"])
            b_rec.append(bm["recall"])

        ci_f1 = [round(float(np.percentile(b_f1, 2.5)), 4), round(float(np.percentile(b_f1, 97.5)), 4)]
        ci_ap = [round(float(np.percentile(b_ap, 2.5)), 4), round(float(np.percentile(b_ap, 97.5)), 4)]
        ci_prec = [round(float(np.percentile(b_prec, 2.5)), 4), round(float(np.percentile(b_prec, 97.5)), 4)]
        ci_rec = [round(float(np.percentile(b_rec, 2.5)), 4), round(float(np.percentile(b_rec, 97.5)), 4)]
    else:
        ci_f1 = [overall["f1"], overall["f1"]]
        ci_ap = [overall["ap"], overall["ap"]]
        ci_prec = [overall["precision"], overall["precision"]]
        ci_rec = [overall["recall"], overall["recall"]]

    report = {
        "split": selected_split,
        "detector_backend": detector.backend,
        "confidence": detector_conf,
        "stride": detector_stride,
        "frames_evaluated": len(eval_images),
        "clip_groups": len(groups),
        "fps": fps,
        "latency_ms": latency_ms,
        "overall": {
            **overall,
            "f1_ci95": ci_f1,
            "ap_ci95": ci_ap,
            "precision_ci95": ci_prec,
            "recall_ci95": ci_rec,
        },
        "by_condition": cond_metrics,
        "by_size": size_metrics,
    }

    return report


def print_report_table(rep: Dict):
    ov = rep["overall"]
    print("\n" + "=" * 70)
    print(f" ARGUS VEHICLE DETECTION EVALUATION REPORT")
    print(f" Split: {rep['split'].upper()} | Detector: {rep['detector_backend']} | Conf: {rep['confidence']}")
    print(f" Frames: {rep['frames_evaluated']} | Clip Groups: {rep['clip_groups']} | Speed: {rep['fps']} FPS ({rep['latency_ms']} ms/frame)")
    print("=" * 70)
    print(f"{'Metric':<14} {'Value':<10} {'95% CI (Bootstrap)'}")
    print("-" * 70)
    print(f"{'Precision':<14} {ov['precision']:<10.4f} [{ov['precision_ci95'][0]:.4f}, {ov['precision_ci95'][1]:.4f}]")
    print(f"{'Recall':<14} {ov['recall']:<10.4f} [{ov['recall_ci95'][0]:.4f}, {ov['recall_ci95'][1]:.4f}]")
    print(f"{'F1 Score':<14} {ov['f1']:<10.4f} [{ov['f1_ci95'][0]:.4f}, {ov['f1_ci95'][1]:.4f}]")
    print(f"{'AP @ 0.50':<14} {ov['ap']:<10.4f} [{ov['ap_ci95'][0]:.4f}, {ov['ap_ci95'][1]:.4f}]")
    print(f"Counts: TP={ov['tp']}, FP={ov['fp']}, FN={ov['fn']}, Total GT={ov['gt']}")

    print("\n" + "-" * 70)
    print(f" Breakdown by Environmental Condition:")
    print(f"{'Condition':<12} {'Precision':<10} {'Recall':<10} {'F1':<10} {'AP@0.5':<10} {'GT Count'}")
    print("-" * 70)
    for c, m in rep["by_condition"].items():
        print(f"{c:<12} {m['precision']:<10.4f} {m['recall']:<10.4f} {m['f1']:<10.4f} {m['ap']:<10.4f} {m['gt']}")

    print("\n" + "-" * 70)
    print(f" Breakdown by Object Size Bucket:")
    print(f"{'Bucket':<12} {'Precision':<10} {'Recall':<10} {'F1':<10} {'AP@0.5':<10} {'GT Count'}")
    print("-" * 70)
    for s, m in rep["by_size"].items():
        print(f"{s:<12} {m['precision']:<10.4f} {m['recall']:<10.4f} {m['f1']:<10.4f} {m['ap']:<10.4f} {m['gt']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Argus Detector Evaluation")
    parser.add_argument("--split", choices=["validation", "val", "test", "all"], default="validation", help="Split to evaluate")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold")
    parser.add_argument("--stride", type=int, default=1, help="Frame stride")
    parser.add_argument("--bootstrap", type=int, default=1000, help="Bootstrap iterations for 95% CI")
    parser.add_argument("--json", type=str, default="", help="Optional output JSON path")
    args = parser.parse_args()

    results = run_evaluation(
        split=args.split,
        detector_conf=args.conf,
        detector_stride=args.stride,
        bootstrap_iterations=args.bootstrap
    )
    print_report_table(results)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Exported JSON metrics to: {args.json}")

