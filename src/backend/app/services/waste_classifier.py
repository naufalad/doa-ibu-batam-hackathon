"""Bridges the API to the segmentation + classification pipeline.

Wraps `pipeline/segment_classify.py` behind a small, lazily-initialized
singleton so the (fairly heavy) Mask2Former + ViT models are only loaded
once per process, the first time a request actually needs them.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PIL import Image

PIPELINE_DIR = Path(__file__).resolve().parent.parent.parent / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.append(str(PIPELINE_DIR))


class WasteClassifierService:
    """Lazy singleton around the segmentation/classification models."""

    _instance: "WasteClassifierService | None" = None

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._loaded = False
        self._seg_processor = None
        self._seg_model = None
        self._cls_processor = None
        self._cls_model = None

    @classmethod
    def get(cls, device: str = "cpu") -> "WasteClassifierService":
        if cls._instance is None:
            cls._instance = cls(device=device)
        return cls._instance

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        # NOTE: this blocks on first call — model weights are cached locally
        # (huggingface hub cache) after the first download, but loading onto
        # `self.device` still takes a few seconds. Consider warming this up
        # via a FastAPI startup event instead of lazy-loading on request #1.
        from segment_classify import load_models

        (
            self._seg_processor,
            self._seg_model,
            self._cls_processor,
            self._cls_model,
        ) = load_models(self.device)
        self._loaded = True

    def classify_image(
        self,
        image_path: str,
        score_threshold: float = 0.5,
        min_area_frac: float = 0.0015,
        topk: int = 3,
    ) -> dict[str, Any]:
        """Run the segment -> crop -> classify pipeline on one image.

        Returns a JSON-serializable report shaped like:
            {"image": ..., "image_size": [w, h], "num_objects": N, "objects": [...]}
        matching `app.schemas.waste.WasteObjectPrediction` per object. This
        mirrors `segment_classify.run()`'s report but skips writing the
        overlay/grid/crop image files to disk, since the API only needs the
        JSON for now.
        """
        self._ensure_loaded()

        from segment_classify import classify_crop, crop_instance, segment_instances

        image = Image.open(image_path).convert("RGB")

        instances = segment_instances(
            image,
            self._seg_processor,
            self._seg_model,
            self.device,
            score_threshold,
            min_area_frac,
        )

        objects: list[dict[str, Any]] = []
        for idx, inst in enumerate(instances, start=1):
            masked_crop, _raw_crop = crop_instance(image, inst)
            waste_preds = classify_crop(masked_crop, self._cls_processor, self._cls_model, self.device, topk)
            top = waste_preds[0]
            objects.append(
                {
                    "index": idx,
                    "coco_label": inst["coco_label"],
                    "segmentation_score": round(inst["seg_score"], 4),
                    "bbox_xyxy": inst["bbox"],
                    "waste_label": top["label"],
                    "waste_confidence": round(top["prob"], 4),
                    "waste_topk": [{"label": p["label"], "prob": round(p["prob"], 4)} for p in waste_preds],
                }
            )

        return {
            "image": image_path,
            "image_size": [image.width, image.height],
            "num_objects": len(objects),
            "objects": objects,
        }
