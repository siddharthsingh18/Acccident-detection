#!/usr/bin/env python3
"""
DoTA Dataset Annotations Downloader and Verifier.
Downloads DoTA_annotations.zip, verifies its SHA-256 checksum,
and extracts annotation JSONs to the target directory.
"""
import argparse
import hashlib
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

EXPECTED_SHA256 = "56209f87398cbf47b9eeee4b516461e71cd3f97f9dd8c4432773315db307ff15"
DEFAULT_URL = (
    "https://raw.githubusercontent.com/MoonBlvd/Detection-of-Traffic-Anomaly/master/dataset/DoTA_annotations.zip"
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = ROOT_DIR / "data" / "DoTA"


def compute_sha256(file_path: Path) -> str:
    """Compute the SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest_path: Path):
    """Download a file with console progress indicator."""
    print(f"Downloading {url} to {dest_path}...")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(".tmp")

    def report_hook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100.0, downloaded * 100.0 / total_size)
            sys.stdout.write(f"\r  Progress: {percent:5.1f}% ({downloaded / (1024*1024):.2f} MB / {total_size / (1024*1024):.2f} MB)")
        else:
            sys.stdout.write(f"\r  Downloaded: {downloaded / (1024*1024):.2f} MB")
        sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, temp_path, reporthook=report_hook)
        print()
        temp_path.rename(dest_path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to download {url}: {e}") from e


def verify_and_extract(
    zip_path: Path,
    extract_to: Path,
    expected_sha256: str = EXPECTED_SHA256,
    extract: bool = True,
) -> bool:
    """Verify SHA-256 and extract annotations archive."""
    if not zip_path.exists():
        print(f"Error: Archive not found at {zip_path}")
        return False

    print(f"Verifying SHA-256 for {zip_path}...")
    actual_sha256 = compute_sha256(zip_path)
    if actual_sha256 != expected_sha256:
        print(f"Error: Checksum mismatch!")
        print(f"  Expected: {expected_sha256}")
        print(f"  Actual:   {actual_sha256}")
        return False

    print(f"✓ Checksum verified ({actual_sha256[:12]}...).")

    if extract:
        print(f"Extracting to {extract_to}...")
        extract_to.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_to)
        print(f"✓ Extraction complete.")

    return True


def main():
    parser = argparse.ArgumentParser(description="Download and verify DoTA dataset annotations.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory to store downloaded archive and extracted files.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_URL,
        help="Download URL for DoTA_annotations.zip.",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Only download and verify without extracting.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing archive without downloading.",
    )
    args = parser.parse_args()

    zip_path = args.data_dir / "DoTA_annotations.zip"
    extract_to = args.data_dir

    if args.verify_only:
        success = verify_and_extract(zip_path, extract_to, extract=not args.no_extract)
        sys.exit(0 if success else 1)

    if zip_path.exists():
        actual_sha256 = compute_sha256(zip_path)
        if actual_sha256 == EXPECTED_SHA256:
            print(f"✓ Existing archive at {zip_path} is valid.")
            if not args.no_extract:
                verify_and_extract(zip_path, extract_to, extract=True)
            sys.exit(0)
        else:
            print(f"Existing archive checksum invalid ({actual_sha256}). Re-downloading...")

    download_file(args.url, zip_path)
    success = verify_and_extract(zip_path, extract_to, extract=not args.no_extract)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

