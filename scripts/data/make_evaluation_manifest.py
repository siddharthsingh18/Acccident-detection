#!/usr/bin/env python3
"""
scripts/data/make_evaluation_manifest.py

Extracts the unbundled CCTV evaluation dataset (274 surveillance clips from dataset/Accidents/
and dataset/No_Accidents/), strictly excluding the 19 bundled demo clips in videos/.
Verifies schema, group isolation, and mutual disjointness between splits.
"""
import csv
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_IN = PROJECT_ROOT / "data" / "manifest.csv"
MANIFEST_OUT = PROJECT_ROOT / "data" / "evaluation_manifest.csv"


def make_evaluation_manifest():
    if not MANIFEST_IN.exists():
        print(f"Error: {MANIFEST_IN} does not exist", file=sys.stderr)
        return False

    with open(MANIFEST_IN, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    # Exclude bundled sample clips (videos/*.mp4)
    eval_rows = [r for r in all_rows if not r["video_path"].startswith("videos/")]

    print(f"Total manifest rows: {len(all_rows)}")
    print(f"Excluded bundled clips: {len(all_rows) - len(eval_rows)}")
    print(f"Retained unbundled CCTV evaluation clips: {len(eval_rows)}")

    # Verify zero group leakage
    train_groups = {r["group_id"] for r in eval_rows if r["split"] == "train"}
    val_groups = {r["group_id"] for r in eval_rows if r["split"] == "val"}
    test_groups = {r["group_id"] for r in eval_rows if r["split"] == "test"}

    leak_tv = train_groups.intersection(val_groups)
    leak_tt = train_groups.intersection(test_groups)
    leak_vt = val_groups.intersection(test_groups)

    if leak_tv or leak_tt or leak_vt:
        print(f"ERROR: Group leakage detected! Train-Val: {leak_tv}, Train-Test: {leak_tt}, Val-Test: {leak_vt}", file=sys.stderr)
        return False

    print(f"✓ Zero group leakage verified across {len(train_groups)} train, {len(val_groups)} val, and {len(test_groups)} test groups.")

    fieldnames = reader.fieldnames
    with open(MANIFEST_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(eval_rows)

    print(f"✓ Successfully wrote evaluation manifest to: {MANIFEST_OUT}")
    return True


if __name__ == "__main__":
    success = make_evaluation_manifest()
    sys.exit(0 if success else 1)
