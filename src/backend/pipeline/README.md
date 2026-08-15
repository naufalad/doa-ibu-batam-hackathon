# Mixed-garbage segmentation + classification pipeline

Proof-of-concept for the "photo of mixed garbage in → sorted-by-item-with-labels
out" step of Pilahin: given one photo containing several pieces of trash, it
finds each object, crops it out, and classifies what kind of waste it is.

```
photo of mixed garbage
        │
        ▼
1. SEGMENT  — Mask2Former (instance segmentation)
        │      finds every object + a pixel mask for each one
        ▼
2. CROP     — for each object, mask out everything except that
        │      object, crop to its bounding box
        ▼
3. CLASSIFY — ViT waste-classifier
        │      labels each crop: plastic / paper / metal / glass /
        ▼      cardboard / biological / battery / clothes / trash / ...
   annotated image + JSON report
```

## Models

| Step | Model | Size | Notes |
|---|---|---|---|
| Segmentation | [`facebook/mask2former-swin-tiny-coco-instance`](https://huggingface.co/facebook/mask2former-swin-tiny-coco-instance) | Swin-Tiny backbone, ~47M params | Instance segmentation over the 80 COCO "thing" classes (bottle, cup, banana, apple, backpack, book, ...) |
| Classification | [`watersplash/waste-classification`](https://huggingface.co/watersplash/waste-classification) | ViT-Base, ~86M params | 12 waste classes: battery, biological, brown/green/white-glass, cardboard, clothes, metal, paper, plastic, shoes, trash |

**Why not the suggested `qubvel-hf/finetune-instance-segmentation-ade20k-mini-mask2former`
model?** It's a tutorial fine-tune with only **2** output classes (`person`,
`car`) — it was trained on a "mini" ADE20K subset to demonstrate the
Mask2Former fine-tuning recipe, not to segment general objects. It can't find
bottles, cups, food scraps, etc., so it isn't useful for this task. We swapped
in `facebook/mask2former-swin-tiny-coco-instance` instead: same size class
(Swin-Tiny backbone) and still a lightweight CPU-friendly model, but trained
on all 80 COCO categories, several of which are exactly the kinds of items
that show up as litter (bottle, cup, banana, apple, backpack, book, vase...).

The segmentation model's own class name (e.g. "bottle") is only used to (a)
filter out non-waste detections like people, and (b) label crops for
readability — the actual waste category always comes from the dedicated
waste-classification model, per the brief ("use this model to classify the
image inside segmentation").

## Setup

```bash
python3 -m venv .venv        # from the repo root
source .venv/bin/activate
pip install -r pipeline/requirements.txt   # torch, transformers, pillow, scipy, ...
```

First run downloads both models from Hugging Face (~450MB combined) and
caches them under `~/.cache/huggingface`.

## Usage

```bash
cd pipeline
python3 segment_classify.py --image images/input/trash_bin_mixed_waste.jpg
```

Outputs land in `images/output/`:

- `<name>_segmented.jpg` — original photo with a numbered, colored mask +
  label per detected object (`#3 plastic (97%)`). People are shown greyed
  out with a "not waste" tag rather than classified.
- `<name>_results_grid.jpg` — contact sheet of every cropped object next to
  its predicted waste category, for a quick before/after look.
- `<name>_crops/obj_NN_<coco-label>_<waste-label>.jpg` — each individual
  crop, saved separately.
- `<name>_report.json` — machine-readable report: per-object bounding box,
  segmentation confidence, waste label + confidence, and top-k alternatives;
  plus a list of detections excluded from waste-sorting (e.g. people).

Useful flags:

```bash
--score-threshold 0.5     # min segmentation confidence to keep an instance
--min-area-frac 0.0015    # drop instances smaller than this fraction of the image
--topk 3                  # how many waste-class candidates to record per object
--device cpu|mps|cuda
```

## Example result

Input: an overflowing public trash bin (bottles, cups, apples, wrappers —
[CC BY 2.0, woodleywonderworks](https://www.flickr.com/photos/73645804@N00/1508921362),
see `images/input/CREDITS.md`).

The pipeline finds 15 instances, skips the 2 people in frame, and classifies
the remaining 13 objects — mostly bottles/cups as `plastic`, apples as
`biological`, plus a few noisier calls (e.g. one bottle read as `metal`) that
reflect the small waste-classifier's real accuracy rather than a pipeline bug.

## Integration

`app/services/waste_classifier.py` imports `load_models()` and `run()` from
this module to serve the `/api/v1/waste/submit` endpoint — see that file for
the (currently stubbed) wiring.
