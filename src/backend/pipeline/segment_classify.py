"""
Mixed-garbage segmentation + classification demo pipeline.

Given a photo containing many mixed garbage objects, this script:

  1. SEGMENTS the image into individual object instances using a lightweight
     Mask2Former (Swin-Tiny backbone, ~47M params) instance-segmentation model.
  2. Crops out each detected object (background masked out, so only the
     object's own pixels are shown to the next model).
  3. CLASSIFIES each cropped object into a waste category (battery,
     biological, cardboard, glass, metal, paper, plastic, shoes/clothes,
     trash, ...) using a ViT waste-classifier.
  4. Saves an annotated overview image, a results grid, and a JSON report.

Models
------
Segmentation:   facebook/mask2former-swin-tiny-coco-instance
    NOTE: the brief suggested qubvel-hf/finetune-instance-segmentation-
    ade20k-mini-mask2former, but that checkpoint is a 2-class (person/car)
    tutorial fine-tune, so it can't localize generic litter. This script
    instead uses Meta's Mask2Former fine-tuned on full COCO-instance (80
    "thing" classes incl. bottle, cup, banana, apple, backpack, book, ...),
    which is the same size class of model (Swin-Tiny, ~47M params) but
    actually useful for spotting everyday waste objects in a photo.

Classification: watersplash/waste-classification (ViT-Base, 12 classes)

Usage
-----
    python segment_classify.py --image images/input/trash_bin_mixed_waste.jpg
"""

from __future__ import annotations

import argparse
import json
import colorsys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
    
from transformers import (
    AutoImageProcessor,
    AutoModelForImageClassification,
    Mask2FormerForUniversalSegmentation,
)

SEG_MODEL_ID = "facebook/mask2former-swin-tiny-coco-instance"
CLS_MODEL_ID = "watersplash/waste-classification"

# COCO "thing" labels that are basically never litter/waste in a trash-sorting
# scene (people, vehicles, animals, furniture...). We keep every detection in
# the JSON report, but these are excluded from the "objects to classify as
# waste" step so we don't ask the waste-classifier to label a human being.
NON_WASTE_LABELS = {
    "person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train",
    "truck", "boat", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "chair", "sofa", "pottedplant",
    "bed", "diningtable", "toilet", "tvmonitor",
}


def load_models(device: str):
    print(f"Loading segmentation model: {SEG_MODEL_ID}")
    seg_processor = AutoImageProcessor.from_pretrained(SEG_MODEL_ID)
    seg_model = Mask2FormerForUniversalSegmentation.from_pretrained(SEG_MODEL_ID)
    seg_model.to(device).eval()

    print(f"Loading waste classification model: {CLS_MODEL_ID}")
    cls_processor = AutoImageProcessor.from_pretrained(CLS_MODEL_ID)
    cls_model = AutoModelForImageClassification.from_pretrained(CLS_MODEL_ID)
    cls_model.to(device).eval()

    return seg_processor, seg_model, cls_processor, cls_model


def segment_instances(
    image: Image.Image,
    seg_processor,
    seg_model,
    device: str,
    score_threshold: float = 0.5,
    min_area_frac: float = 0.0015,
):
    """Run instance segmentation and return a list of per-object dicts."""
    inputs = seg_processor(images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = seg_model(**inputs)

    result = seg_processor.post_process_instance_segmentation(
        outputs, threshold=score_threshold, target_sizes=[(image.height, image.width)]
    )[0]

    segmentation = result["segmentation"].cpu().numpy()  # HxW, -1 = background
    segments_info = result["segments_info"]
    id2label = seg_model.config.id2label
    img_area = image.width * image.height

    instances = []
    for seg in segments_info:
        mask = segmentation == seg["id"]
        area = int(mask.sum())
        if area == 0 or area / img_area < min_area_frac:
            continue
        ys, xs = np.where(mask)
        bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        instances.append(
            {
                "seg_id": int(seg["id"]),
                "coco_label": id2label[seg["label_id"]],
                "seg_score": float(seg["score"]),
                "mask": mask,
                "bbox": bbox,
                "area_px": area,
                "area_frac": area / img_area,
            }
        )

    instances.sort(key=lambda d: -d["area_px"])
    return instances


def crop_instance(image: Image.Image, inst: dict, pad_frac: float = 0.04, bg=(255, 255, 255)):
    """Return (masked_crop, raw_crop) for one instance, background pixels flattened."""
    W, H = image.size
    x0, y0, x1, y1 = inst["bbox"]
    w, h = x1 - x0, y1 - y0
    padx, pady = int(w * pad_frac) + 2, int(h * pad_frac) + 2
    x0p, y0p = max(0, x0 - padx), max(0, y0 - pady)
    x1p, y1p = min(W, x1 + padx + 1), min(H, y1 + pady + 1)

    np_img = np.array(image.convert("RGB"))
    masked = np_img.copy()
    masked[~inst["mask"]] = bg
    masked_img = Image.fromarray(masked)

    masked_crop = masked_img.crop((x0p, y0p, x1p, y1p))
    raw_crop = image.crop((x0p, y0p, x1p, y1p))
    return masked_crop, raw_crop


def classify_crop(crop: Image.Image, cls_processor, cls_model, device: str, topk: int = 3):
    inputs = cls_processor(images=crop.convert("RGB"), return_tensors="pt").to(device)
    with torch.no_grad():
        logits = cls_model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    k = min(topk, probs.shape[-1])
    top_probs, top_idx = probs.topk(k)
    id2label = cls_model.config.id2label
    return [
        {"label": id2label[int(i)], "prob": float(p)}
        for p, i in zip(top_probs.tolist(), top_idx.tolist())
    ]


def distinct_colors(n: int):
    colors = []
    for i in range(n):
        h = i / max(n, 1)
        r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.95)
        colors.append((int(r * 255), int(g * 255), int(b * 255)))
    return colors


def draw_overlay(image: Image.Image, results: list[dict], excluded: list[dict] | None = None) -> Image.Image:
    """Draw semi-transparent mask fills + numbered boxes for each classified object.

    `excluded` (e.g. detected people) are drawn with a neutral grey outline
    and no waste label, so it's clear they were seen but intentionally not
    waste-sorted.
    """
    excluded = excluded or []
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    colors = distinct_colors(len(results))

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22
        )
        small_font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial.ttf", 16
        )
    except OSError:
        font = ImageFont.load_default()
        small_font = font

    for res, color in zip(results, colors):
        mask = res["mask"]
        color_layer = np.zeros((*mask.shape, 4), dtype=np.uint8)
        color_layer[mask] = (*color, 90)
        overlay = Image.alpha_composite(overlay, Image.fromarray(color_layer, "RGBA"))
    for exc in excluded:
        mask = exc["mask"]
        color_layer = np.zeros((*mask.shape, 4), dtype=np.uint8)
        color_layer[mask] = (150, 150, 150, 60)
        overlay = Image.alpha_composite(overlay, Image.fromarray(color_layer, "RGBA"))

    draw = ImageDraw.Draw(overlay)
    for idx, (res, color) in enumerate(zip(results, colors), start=1):
        x0, y0, x1, y1 = res["bbox"]
        draw.rectangle([x0, y0, x1, y1], outline=(*color, 255), width=3)
        label = f"#{idx} {res['waste_label']} ({res['waste_prob']:.0%})"
        text_w = draw.textlength(label, font=font)
        draw.rectangle(
            [x0, max(0, y0 - 26), x0 + text_w + 10, max(0, y0 - 26) + 26],
            fill=(*color, 230),
        )
        draw.text((x0 + 5, max(0, y0 - 26)), label, fill=(0, 0, 0, 255), font=font)
    for exc in excluded:
        x0, y0, x1, y1 = exc["bbox"]
        draw.rectangle([x0, y0, x1, y1], outline=(150, 150, 150, 255), width=2)
        label = f"{exc['coco_label']} (not waste)"
        text_w = draw.textlength(label, font=small_font)
        draw.rectangle(
            [x0, max(0, y0 - 20), x0 + text_w + 8, max(0, y0 - 20) + 20],
            fill=(150, 150, 150, 200),
        )
        draw.text((x0 + 4, max(0, y0 - 20)), label, fill=(255, 255, 255, 255), font=small_font)

    return Image.alpha_composite(base, overlay).convert("RGB")


def build_results_grid(results: list[dict], cols: int = 5) -> Image.Image:
    """Small contact-sheet of every classified crop with its predicted label."""
    if not results:
        return Image.new("RGB", (400, 100), (255, 255, 255))

    thumb = 200
    pad = 14
    label_h = 46
    rows = (len(results) + cols - 1) // cols
    W = cols * (thumb + pad) + pad
    H = rows * (thumb + label_h + pad) + pad
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 15)
        small_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
        small_font = font

    colors = distinct_colors(len(results))
    for idx, (res, color) in enumerate(zip(results, colors)):
        r, c = divmod(idx, cols)
        x = pad + c * (thumb + pad)
        y = pad + r * (thumb + label_h + pad)

        crop = res["raw_crop"].copy()
        crop.thumbnail((thumb, thumb))
        cx = x + (thumb - crop.width) // 2
        cy = y + (thumb - crop.height) // 2
        sheet.paste(crop, (cx, cy))
        draw.rectangle([x, y, x + thumb, y + thumb], outline=color, width=4)

        line1 = f"#{idx + 1} {res['coco_label']}"
        line2 = f"{res['waste_label']} ({res['waste_prob']:.0%})"
        draw.text((x, y + thumb + 4), line1, fill=(60, 60, 60), font=small_font)
        draw.text((x, y + thumb + 22), line2, fill=(0, 0, 0), font=font)

    return sheet


def run(
    image_path: str,
    out_dir: str,
    device: str = "cpu",
    score_threshold: float = 0.5,
    min_area_frac: float = 0.0015,
    topk: int = 3,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(image_path).stem

    image = Image.open(image_path).convert("RGB")
    print(f"Loaded {image_path} ({image.width}x{image.height})")

    seg_processor, seg_model, cls_processor, cls_model = load_models(device)

    print("Step 1/3: segmenting instances ...")
    instances = segment_instances(
        image, seg_processor, seg_model, device, score_threshold, min_area_frac
    )
    print(f"  -> {len(instances)} instance(s) above threshold {score_threshold}")

    print("Step 2/3: cropping + classifying each object ...")
    results = []
    excluded = []
    for inst in instances:
        if inst["coco_label"] in NON_WASTE_LABELS:
            # Detected (e.g. a person in the shot) but not something to
            # waste-sort — skip classification, keep it for the record.
            excluded.append(inst)
            print(f"  skipped: coco='{inst['coco_label']}' (not a waste item)")
            continue
        masked_crop, raw_crop = crop_instance(image, inst)
        waste_preds = classify_crop(masked_crop, cls_processor, cls_model, device, topk)
        results.append(
            {
                **inst,
                "masked_crop": masked_crop,
                "raw_crop": raw_crop,
                "waste_label": waste_preds[0]["label"],
                "waste_prob": waste_preds[0]["prob"],
                "waste_topk": waste_preds,
            }
        )
        print(
            f"  #{len(results)}: coco='{inst['coco_label']}' "
            f"(seg_score={inst['seg_score']:.2f}) -> waste='{results[-1]['waste_label']}' "
            f"({results[-1]['waste_prob']:.0%})"
        )

    print("Step 3/3: rendering outputs ...")
    overlay_img = draw_overlay(image, results, excluded)
    overlay_path = out_dir / f"{stem}_segmented.jpg"
    overlay_img.save(overlay_path, quality=92)

    grid_img = build_results_grid(results)
    grid_path = out_dir / f"{stem}_results_grid.jpg"
    grid_img.save(grid_path, quality=92)

    crops_dir = out_dir / f"{stem}_crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    for idx, res in enumerate(results, start=1):
        safe_label = res["waste_label"].replace(" ", "_")
        res["masked_crop"].save(
            crops_dir / f"obj_{idx:02d}_{res['coco_label']}_{safe_label}.jpg", quality=90
        )

    report = {
        "image": str(image_path),
        "image_size": [image.width, image.height],
        "segmentation_model": SEG_MODEL_ID,
        "classification_model": CLS_MODEL_ID,
        "score_threshold": score_threshold,
        "min_area_frac": min_area_frac,
        "num_objects": len(results),
        "objects": [
            {
                "index": idx + 1,
                "coco_label": r["coco_label"],
                "segmentation_score": round(r["seg_score"], 4),
                "bbox_xyxy": r["bbox"],
                "area_px": r["area_px"],
                "area_frac": round(r["area_frac"], 5),
                "waste_label": r["waste_label"],
                "waste_confidence": round(r["waste_prob"], 4),
                "waste_topk": [
                    {"label": p["label"], "prob": round(p["prob"], 4)} for p in r["waste_topk"]
                ],
            }
            for idx, r in enumerate(results)
        ],
        "excluded_detections": [
            {
                "coco_label": e["coco_label"],
                "segmentation_score": round(e["seg_score"], 4),
                "bbox_xyxy": e["bbox"],
                "reason": "not a waste item",
            }
            for e in excluded
        ],
    }
    report_path = out_dir / f"{stem}_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print("\nDone.")
    print(f"  Segmented overlay : {overlay_path}")
    print(f"  Results grid      : {grid_path}")
    print(f"  Per-object crops  : {crops_dir}")
    print(f"  JSON report       : {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True, help="Path to input image with many mixed garbage objects")
    parser.add_argument("--out-dir", default="images/output", help="Directory to write outputs into")
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps", "cuda"])
    parser.add_argument("--score-threshold", type=float, default=0.5, help="Min segmentation confidence")
    parser.add_argument(
        "--min-area-frac", type=float, default=0.0015, help="Drop instances smaller than this fraction of the image"
    )
    parser.add_argument("--topk", type=int, default=3, help="How many waste-class candidates to keep per object")
    args = parser.parse_args()

    run(
        image_path=args.image,
        out_dir=args.out_dir,
        device=args.device,
        score_threshold=args.score_threshold,
        min_area_frac=args.min_area_frac,
        topk=args.topk,
    )


if __name__ == "__main__":
    main()
