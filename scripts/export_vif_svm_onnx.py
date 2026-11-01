#!/usr/bin/env python3
"""
Export script: Convert legacy VIF+SVM (scikit-learn SVC model) to ONNX format.
Handles cross-version backward compatibility (scikit-learn 0.22 -> modern scikit-learn).
Outputs: artifacts/models/vif_svm.onnx (or specified output path).
"""
import argparse
import logging
import os
from pathlib import Path
import pickle
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export_vif_svm")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def export_vif_svm(input_path: Path, output_path: Path) -> bool:
    """Load legacy SVM pickle, patch scikit-learn 1.x compatibility, export to ONNX, verify parity."""
    if not input_path.exists():
        logger.error(f"Input SVM model not found at {input_path}")
        return False

    logger.info(f"Loading legacy SVM model from {input_path}...")
    with open(input_path, "rb") as f:
        model = pickle.load(f)

    # Patch backward compatibility for modern scikit-learn
    if "probA_" in model.__dict__ and not hasattr(model, "_probA"):
        model._probA = model.__dict__["probA_"]
    if "probB_" in model.__dict__ and not hasattr(model, "_probB"):
        model._probB = model.__dict__["probB_"]

    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
        import onnxruntime as ort
    except ImportError as e:
        logger.error(f"Missing ONNX conversion dependency: {e}. Run pip install skl2onnx onnxruntime onnx.")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    initial_type = [("float_input", FloatTensorType([None, 304]))]
    logger.info("Converting scikit-learn SVC to ONNX...")
    onx = convert_sklearn(model, initial_types=initial_type, target_opset=15)

    with open(output_path, "wb") as f:
        f.write(onx.SerializeToString())
    logger.info(f"Saved ONNX model to {output_path} ({output_path.stat().st_size} bytes)")

    # Parity verification
    np.random.seed(42)
    test_vectors = np.random.randn(20, 304).astype(np.float32)

    skl_preds = model.predict(test_vectors)
    sess = ort.InferenceSession(str(output_path))
    input_name = sess.get_inputs()[0].name
    ort_outs = sess.run(None, {input_name: test_vectors})
    ort_preds = ort_outs[0]

    matches = np.array_equal(skl_preds, ort_preds)
    match_rate = np.mean(skl_preds == ort_preds) * 100.0
    logger.info(f"Parity check: {match_rate:.1f}% predictions matched across {len(test_vectors)} test vectors.")

    if not matches:
        logger.error("ONNX predictions deviated from scikit-learn model!")
        return False

    logger.info("ONNX export and parity verification completed successfully.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export VIF SVM to ONNX")
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "VIF" / "model-svm1.sav",
        help="Path to legacy VIF SVM pickle",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "models" / "vif_svm.onnx",
        help="Path for exported ONNX model",
    )
    args = parser.parse_args()
    success = export_vif_svm(args.input, args.output)
    exit(0 if success else 1)
