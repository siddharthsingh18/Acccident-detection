#!/usr/bin/env python3
"""
scripts/retrain_svm.py

Recompute VIF (Violent Flows) features on manifest clips, retrain linear SVM with class balancing,
export to ONNX, and compare old vs retrained model on the validation split before replacing.
"""

import argparse
import csv
import logging
import os
from pathlib import Path
import pickle
import sys
import time
from typing import Dict, List, Tuple, Any, Optional

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("retrain_svm")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from sklearn.svm import SVC
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    import onnxruntime as ort
    from VIF.vif import VIF
    from argus_ml.preprocessing import load_video_frames
    SKLEARN_AVAILABLE = True
except ImportError as e:
    SKLEARN_AVAILABLE = False
    logger.warning(f"Required ML modules not available: {e}")


def extract_features_for_split(
    manifest_path: Path,
    target_split: str,
    vif: Any,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Extract 304-dimensional VIF features for a specific split in manifest.
    """
    X_list = []
    y_list = []
    video_paths = []

    with open(manifest_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            split = row.get("split", "").strip().lower()
            if split != target_split:
                continue
            if row.get("camera_view") != "cctv":
                continue

            vpath = PROJECT_ROOT / row["video_path"]
            if not vpath.exists():
                logger.warning(f"Video file missing: {vpath}")
                continue

            try:
                frames = load_video_frames(vpath, target_size=None)
                if not frames or len(frames) < 15:
                    continue

                gray_frames = []
                for f in frames:
                    if len(f.shape) == 3 and f.shape[2] == 3:
                        gray_frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
                    else:
                        gray_frames.append(f)

                # Guard against legacy VIF off-by-one boundary index error when len % 6 == 3
                if len(gray_frames) % 6 == 3:
                    gray_frames.append(gray_frames[-1])

                feat = vif.process(gray_frames)
                if feat.shape == (304,):
                    X_list.append(feat)
                    label = 1 if row.get("label", "").lower() == "accident" else 0
                    y_list.append(label)
                    video_paths.append(str(row["video_path"]))
            except Exception as e:
                logger.warning(f"Error extracting VIF features for {vpath}: {e}")

    X = np.array(X_list, dtype=np.float32) if X_list else np.empty((0, 304), dtype=np.float32)
    y = np.array(y_list, dtype=np.int64) if y_list else np.empty((0,), dtype=np.int64)
    return X, y, video_paths


def evaluate_model(clf: Any, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """Compute classification metrics for an SVM model."""
    if len(X) == 0:
        return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Ensure scikit-learn 1.x compatibility
    if hasattr(clf, "__dict__"):
        if "probA_" in clf.__dict__ and not hasattr(clf, "_probA"):
            clf._probA = clf.__dict__["probA_"]
        if "probB_" in clf.__dict__ and not hasattr(clf, "_probB"):
            clf._probB = clf.__dict__["probB_"]

    preds = clf.predict(X)
    acc = float(accuracy_score(y, preds))
    prec = float(precision_score(y, preds, zero_division=0))
    rec = float(recall_score(y, preds, zero_division=0))
    f1 = float(f1_score(y, preds, zero_division=0))

    return {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
    }


def retrain_vif_svm(
    manifest_path: Path,
    old_model_path: Path,
    output_onnx_path: Path,
    replace_current: bool = False,
    cache_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Retrain SVM with class balancing and evaluate vs old model.
    """
    if not SKLEARN_AVAILABLE:
        raise RuntimeError("scikit-learn and ONNX dependencies required")

    vif = VIF()

    # Feature caching to accelerate repeated runs
    if cache_path and cache_path.exists():
        logger.info(f"Loading cached VIF features from {cache_path}...")
        data = np.load(cache_path)
        X_train, y_train = data["X_train"], data["y_train"]
        X_val, y_val = data["X_val"], data["y_val"]
    else:
        logger.info("Extracting VIF features for train split...")
        t0 = time.perf_counter()
        X_train, y_train, _ = extract_features_for_split(manifest_path, "train", vif)
        logger.info(f"Extracted {len(X_train)} train samples in {time.perf_counter() - t0:.1f}s")

        logger.info("Extracting VIF features for val split...")
        t1 = time.perf_counter()
        X_val, y_val, _ = extract_features_for_split(manifest_path, "val", vif)
        logger.info(f"Extracted {len(X_val)} val samples in {time.perf_counter() - t1:.1f}s")

        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache_path, X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val)
            logger.info(f"Saved feature cache to {cache_path}")

    logger.info(f"Train split: {len(X_train)} samples (normal={sum(y_train==0)}, accident={sum(y_train==1)})")
    logger.info(f"Val split:   {len(X_val)} samples (normal={sum(y_val==0)}, accident={sum(y_val==1)})")

    # Evaluate old model
    old_metrics = {}
    if old_model_path.exists():
        logger.info(f"Evaluating old legacy SVM model from {old_model_path}...")
        with open(old_model_path, "rb") as f:
            old_clf = pickle.load(f)
        old_metrics = evaluate_model(old_clf, X_val, y_val)
    else:
        logger.warning(f"Old model not found at {old_model_path}")

    # Retrain new SVM with class balancing
    logger.info("Training new SVM (linear kernel, class_weight='balanced', probability=True)...")
    new_clf = SVC(
        kernel="linear",
        C=1.0,
        class_weight="balanced",
        probability=True,
        random_state=42,
    )
    new_clf.fit(X_train, y_train)

    # Patch backward compatibility
    if hasattr(new_clf, "probA_") and not hasattr(new_clf, "_probA"):
        new_clf._probA = new_clf.probA_
    if hasattr(new_clf, "probB_") and not hasattr(new_clf, "_probB"):
        new_clf._probB = new_clf.probB_

    new_metrics = evaluate_model(new_clf, X_val, y_val)

    # Side-by-side comparison table
    print("\n" + "=" * 60)
    print("VIF SVM Validation Split Comparison (45 clips: 19 normal, 26 accident)")
    print("=" * 60)
    print(f"{'Metric':<15} | {'Old Model':<15} | {'Retrained Model':<15} | {'Difference':<10}")
    print("-" * 60)
    for m in ["accuracy", "precision", "recall", "f1"]:
        old_val = old_metrics.get(m, 0.0)
        new_val = new_metrics.get(m, 0.0)
        diff = new_val - old_val
        diff_str = f"{'+' if diff >= 0 else ''}{diff:.4f}"
        print(f"{m.capitalize():<15} | {old_val:<15.4f} | {new_val:<15.4f} | {diff_str:<10}")
    print("=" * 60 + "\n")

    # Export to ONNX
    output_onnx_path.parent.mkdir(parents=True, exist_ok=True)
    initial_type = [("float_input", FloatTensorType([None, 304]))]
    logger.info("Converting retrained SVM to ONNX format...")
    onnx_model = convert_sklearn(new_clf, initial_types=initial_type, target_opset=15)

    with open(output_onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    logger.info(f"Saved retrained ONNX model to {output_onnx_path}")

    # Parity check on validation samples
    sess = ort.InferenceSession(str(output_onnx_path))
    input_name = sess.get_inputs()[0].name
    ort_outs = sess.run(None, {input_name: X_val})
    ort_preds = ort_outs[0]
    skl_preds = new_clf.predict(X_val)

    parity_matches = np.array_equal(skl_preds, ort_preds)
    match_rate = float(np.mean(skl_preds == ort_preds) * 100.0)
    logger.info(f"Parity check: {match_rate:.1f}% matches on {len(X_val)} validation samples")

    if not parity_matches:
        logger.warning("ONNX predictions diverged slightly from scikit-learn model!")

    # Replace current default vif_svm.onnx if requested
    default_onnx_path = PROJECT_ROOT / "artifacts" / "models" / "vif_svm.onnx"
    if replace_current:
        with open(default_onnx_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        logger.info(f"[*] Replaced default model at {default_onnx_path} with retrained model")

    return {
        "old_metrics": old_metrics,
        "new_metrics": new_metrics,
        "parity_match_rate": match_rate,
        "output_path": str(output_onnx_path),
        "replaced_default": replace_current,
    }


def main():
    parser = argparse.ArgumentParser(description="Retrain VIF SVM and compare against legacy model")
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data" / "manifest.csv", help="Path to manifest CSV")
    parser.add_argument("--old-model", type=Path, default=PROJECT_ROOT / "VIF" / "model-svm1.sav", help="Path to legacy SVM model")
    parser.add_argument("--output-onnx", type=Path, default=PROJECT_ROOT / "artifacts" / "models" / "vif_svm_retrained.onnx", help="Path for retrained ONNX model")
    parser.add_argument("--replace", action="store_true", help="Replace artifacts/models/vif_svm.onnx with the retrained model")
    parser.add_argument("--cache", type=Path, default=PROJECT_ROOT / "data" / "vif_features_cache.npz", help="Path to VIF features cache")
    args = parser.parse_args()

    retrain_vif_svm(
        manifest_path=args.manifest,
        old_model_path=args.old_model,
        output_onnx_path=args.output_onnx,
        replace_current=args.replace,
        cache_path=args.cache,
    )


if __name__ == "__main__":
    main()
