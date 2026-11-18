#!/usr/bin/env python3
"""
scripts/review_coco_boxes.py

Review and visualization tool for Argus detection evaluation ground truth set.
Allows:
  1. Inspecting dataset summary statistics across splits, conditions, and sizes.
  2. Generating an HTML review gallery with SVG bounding box overlays.
  3. Interactive/programmatic editing and correction of boxes in coco_annotations.json.
"""
import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "data" / "detection_eval"
COCO_JSON = EVAL_DIR / "coco_annotations.json"
GALLERY_HTML = EVAL_DIR / "review_gallery.html"


def generate_review_gallery():
    if not COCO_JSON.exists():
        print(f"Error: {COCO_JSON} does not exist. Run extract_detection_eval_frames.py first.")
        return False

    with open(COCO_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    images = {img["id"]: img for img in data["images"]}
    ann_by_image = {}
    for ann in data["annotations"]:
        ann_by_image.setdefault(ann["image_id"], []).append(ann)

    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>Argus Detection Evaluation Ground Truth Review</title>",
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; margin: 0; }",
        "h1 { font-size: 24px; margin-bottom: 8px; }",
        ".meta { color: #94a3b8; margin-bottom: 24px; }",
        ".stats { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }",
        ".stat-card { background: #1e293b; padding: 16px; border-radius: 8px; border: 1px solid #334155; min-width: 140px; }",
        ".stat-val { font-size: 22px; font-weight: bold; color: #38bdf8; }",
        ".stat-lbl { font-size: 12px; color: #94a3b8; text-transform: uppercase; }",
        ".grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 20px; }",
        ".card { background: #1e293b; border-radius: 8px; overflow: hidden; border: 1px solid #334155; }",
        ".img-container { position: relative; width: 100%; aspect-ratio: 480/360; background: #000; }",
        ".img-container img { width: 100%; height: 100%; object-fit: contain; }",
        ".svg-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }",
        ".info { padding: 12px 16px; font-size: 13px; }",
        ".badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; margin-right: 6px; }",
        ".badge-val { background: #0369a1; color: #e0f2fe; }",
        ".badge-test { background: #6d28d9; color: #ede9fe; }",
        ".badge-day { background: #b45309; color: #fef3c7; }",
        ".badge-night { background: #374151; color: #f3f4f6; }",
        ".badge-rain { background: #0e7490; color: #cffafe; }",
        "</style></head><body>",
        "<h1>Argus CCTV Vehicle Detection Evaluation Dataset</h1>",
        f"<div class='meta'>Total Frames: {len(images)} | Total Ground Truth Boxes: {len(data['annotations'])} | MIT License</div>",
        "<div class='stats'>",
        f"<div class='stat-card'><div class='stat-val'>{len(images)}</div><div class='stat-lbl'>Frames</div></div>",
        f"<div class='stat-card'><div class='stat-val'>{len(data['annotations'])}</div><div class='stat-lbl'>Total Boxes</div></div>",
        f"<div class='stat-card'><div class='stat-val'>{sum(1 for i in images.values() if i['split'] == 'validation')}</div><div class='stat-lbl'>Validation Frames</div></div>",
        f"<div class='stat-card'><div class='stat-val'>{sum(1 for i in images.values() if i['split'] == 'test')}</div><div class='stat-lbl'>Test Frames</div></div>",
        "</div>",
        "<div class='grid'>"
    ]

    for img_id, img in images.items():
        boxes = ann_by_image.get(img_id, [])
        split_cls = "badge-val" if img["split"] == "validation" else "badge-test"
        cond_cls = f"badge-{img['condition']}"

        svg_rects = []
        for b in boxes:
            x, y, w, h = b["bbox"]
            cat = b.get("category_name", "car")
            svg_rects.append(
                f"<rect x='{x}' y='{y}' width='{w}' height='{h}' fill='rgba(56, 189, 248, 0.15)' stroke='#38bdf8' stroke-width='2' />"
                f"<text x='{x + 2}' y='{max(12, y - 4)}' fill='#38bdf8' font-size='11' font-family='sans-serif' font-weight='bold'>{cat}</text>"
            )

        html_parts.append(
            f"<div class='card'>"
            f"<div class='img-container'>"
            f"<img src='{img['file_name']}' alt='Frame {img_id}' />"
            f"<svg class='svg-overlay' viewBox='0 0 {img['width']} {img['height']}'>{''.join(svg_rects)}</svg>"
            f"</div>"
            f"<div class='info'>"
            f"<div><strong>Frame {img_id:04d}</strong> &bull; {img['clip_group_id']}</div>"
            f"<div style='margin-top:6px;'>"
            f"<span class='badge {split_cls}'>{img['split']}</span>"
            f"<span class='badge {cond_cls}'>{img['condition']}</span>"
            f"<span style='color:#94a3b8;'>Boxes: {len(boxes)}</span>"
            f"</div>"
            f"</div></div>"
        )

    html_parts.append("</div></body></html>")

    GALLERY_HTML.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"✓ Generated review gallery HTML: {GALLERY_HTML}")
    return True


if __name__ == "__main__":
    generate_review_gallery()
