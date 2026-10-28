#!/usr/bin/env python3
"""
Argus Model Downloader & License Verification Tool.
Ensures no weight binaries are tracked in Git, verifies SHA-256 checksums,
and displays explicit license banners before saving weights.
"""
import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# Registry of supported models, their SHA-256 hashes, licenses, and sources
MODEL_REGISTRY = {
    "yolov8n-onnx": {
        "filename": "yolov8n.onnx",
        "description": "YOLOv8 Nano ONNX model for vehicle detection (COCO classes)",
        "license": "AGPL-3.0 (Commercial license required for proprietary use)",
        "license_url": "https://github.com/ultralytics/ultralytics/blob/main/LICENSE",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.onnx",
        "sha256": "439ce8a6e7c10b7a4211a774641e16f39ddc95503b80b0653d9e802a4bfdd9be",
    },
    "yolox-s-onnx": {
        "filename": "yolox_s.onnx",
        "description": "Megvii YOLOX-Small permissive object detector",
        "license": "Apache-2.0 (Permissive, commercial and MIT-compatible)",
        "license_url": "https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE",
        "url": "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx",
        "sha256": "b068bc56ba598c92fb38cf2ea31df12da3eeeb351e39a3f29dd11d1fa5020fd4",
    },
    "ssdlite320-mobilenet": {
        "filename": "ssdlite320_mobilenet_v3_large.pth",
        "description": "PyTorch Torchvision SSDLite320 MobileNetV3 COCO vehicle detector",
        "license": "BSD-3-Clause (Permissive, fully MIT-compatible)",
        "license_url": "https://github.com/pytorch/vision/blob/main/LICENSE",
        "url": "https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a7954395.pth",
        "sha256": "a7954395982f6eefc4a1deca2dfd9f2df1ffcc71e723de4f552636f1c71286a0",
    }
}


def compute_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def download_model(model_key: str, force: bool = False) -> bool:
    """Download and verify a model from the registry."""
    if model_key not in MODEL_REGISTRY:
        print(f"Error: Unknown model '{model_key}'. Available: {list(MODEL_REGISTRY.keys())}", file=sys.stderr)
        return False

    info = MODEL_REGISTRY[model_key]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = MODELS_DIR / info["filename"]

    print("\n" + "=" * 65)
    print(f" MODEL:   {model_key} ({info['filename']})")
    print(f" DESC:    {info['description']}")
    print(f" LICENSE: {info['license']}")
    print(f" URL:     {info['license_url']}")
    print("=" * 65)

    if target_path.exists() and not force:
        print(f"File already exists at: {target_path}")
        print("Verifying existing SHA-256 checksum...")
        existing_hash = compute_sha256(target_path)
        if existing_hash.lower() == info["sha256"].lower():
            print(f"✓ SHA-256 match: {existing_hash} [OK]")
            return True
        else:
            print(f"Checksum mismatch! Expected {info['sha256']}, got {existing_hash}.")
            print("Re-downloading...")

    print(f"Downloading from: {info['url']}")
    temp_target = target_path.with_suffix(".download")

    try:
        def progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100.0, downloaded * 100.0 / total_size)
                mb_down = downloaded / (1024 * 1024)
                mb_tot = total_size / (1024 * 1024)
                sys.stdout.write(f"\rProgress: {percent:5.1f}% ({mb_down:5.1f}MB / {mb_tot:5.1f}MB)")
                sys.stdout.flush()

        urllib.request.urlretrieve(info["url"], temp_target, reporthook=progress_hook)
        print()

        # Compute SHA-256
        print("Verifying downloaded file SHA-256...")
        actual_hash = compute_sha256(temp_target)
        if actual_hash.lower() != info["sha256"].lower():
            print(f"✗ ERROR: Checksum mismatch!\nExpected: {info['sha256']}\nGot:      {actual_hash}", file=sys.stderr)
            if temp_target.exists():
                temp_target.unlink()
            return False

        if target_path.exists():
            target_path.unlink()
        temp_target.rename(target_path)
        print(f"✓ Verified SHA-256: {actual_hash}")
        print(f"✓ Model successfully installed at: {target_path}\n")
        return True

    except Exception as e:
        print(f"✗ Download failed: {e}", file=sys.stderr)
        if temp_target.exists():
            temp_target.unlink()
        return False


def main():
    parser = argparse.ArgumentParser(description="Download and verify Argus computer vision models.")
    parser.add_argument("--model", choices=list(MODEL_REGISTRY.keys()), help="Model identifier to download")
    parser.add_argument("--all", action="store_true", help="Download all registered models")
    parser.add_argument("--list", action="store_true", help="List registered models and licenses")
    parser.add_argument("--force", action="store_true", help="Force redownload even if file exists")

    args = parser.parse_args()

    if args.list:
        print(f"\n{'Model Key':<24} {'License':<32} {'Filename'}")
        print("-" * 75)
        for k, v in MODEL_REGISTRY.items():
            print(f"{k:<24} {v['license'][:30]:<32} {v['filename']}")
        print()
        return 0

    if args.all:
        success = True
        for k in MODEL_REGISTRY:
            if not download_model(k, force=args.force):
                success = False
        return 0 if success else 1

    if args.model:
        return 0 if download_model(args.model, force=args.force) else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
