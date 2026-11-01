import subprocess
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Exact legacy files from original Argus repository that exceed 1MB.
# No newly created or modified files are permitted to exceed 1MB.
LEGACY_LARGE_FILES_ALLOWLIST = {
    "Car_Detection/test.png",
    "Corner_Detection_Module/Easy.mp4",
    "Corner_Detection_Module/Test_Corners.mp4",
    "Documents/Argus.pptx",
    "Documents/Corner Detection - Code Explanation.docx",
    "Documents/Crash Estimation.docx",
    "Documents/GP_document.pdf",
    "Documents/Road trafffic accidents detection based on crash estimation Presentation.pptx",
    "Gif/1508.gif",
    "Gif/1516.gif",
    "Gif/1519.gif",
    "Gif/1543.gif",
    "Gif/1567.gif",
    "Images/BlockDiagram.png",
    "Lucas_Kanade_Tracker/Easy.mp4",
    "Lucas_Kanade_Tracker/Tracking_Demo.avi",
    "Lucas_Kanade_Tracker/output.avi",
    "Lucas_Kanade_Tracker/video.avi",
    "Mosse_Tracker/Easy.mp4",
    "Papers/Visual Object Tracking using Adaptive Correlation Filters - Mosse.pdf",
    "boxes/1601.txt",
    "boxes/1602.txt",
    "boxes/1603.txt",
}

FORBIDDEN_EXTENSIONS = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pt",
    ".pth",
    ".onnx",
    ".h5",
    ".zip",
)


def get_tracked_files() -> list[str]:
    """Retrieve all files currently tracked by git."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_no_forbidden_binary_extensions_tracked():
    """Ensure no database, weights, or archive files are tracked in git."""
    tracked_files = get_tracked_files()
    forbidden = [
        f for f in tracked_files
        if any(f.endswith(ext) for ext in FORBIDDEN_EXTENSIONS)
    ]
    assert not forbidden, (
        f"Forbidden files tracked in git: {forbidden}. "
        "Databases, PyTorch weights, ONNX models, and zip archives must be gitignored."
    )


def test_no_new_tracked_file_larger_than_1mb():
    """Ensure no newly tracked files exceed the 1MB threshold."""
    tracked_files = get_tracked_files()
    violations = []
    max_bytes = 1024 * 1024  # 1 MB

    for rel_path in tracked_files:
        # Allow legacy videos/ and Joiner/vids/ or explicit documents
        if rel_path in LEGACY_LARGE_FILES_ALLOWLIST:
            continue
        if rel_path.startswith("Joiner/vids/") or rel_path.startswith("videos/"):
            continue

        full_path = PROJECT_ROOT / rel_path
        if full_path.is_file():
            size = full_path.stat().st_size
            if size > max_bytes:
                violations.append(f"{rel_path} ({size / (1024 * 1024):.2f} MB)")

    assert not violations, (
        f"The following tracked files exceed the 1 MB repository limit:\n"
        + "\n".join(violations)
        + "\nMove large data to scripts/data/ downloads or manifests."
    )


def test_database_and_data_dir_are_gitignored():
    """Verify that databases and data download folders are ignored by git."""
    ignored_checks = [
        "System/Database/Argus_DB.db",
        "data/DoTA/DoTA_annotations.zip",
        "data/DoTA/annotations/clip.json",
    ]
    for check_path in ignored_checks:
        res = subprocess.run(
            ["git", "check-ignore", check_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Expected {check_path} to be ignored by git."

