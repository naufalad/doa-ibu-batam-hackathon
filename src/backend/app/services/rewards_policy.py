"""Point-range policy for waste tokens.

Still a stand-in for real market rates per kg per material (nothing in
this repo or `app/db.py` sources those numbers yet — once product hands
over actual per-material rates, replace `_BASE_RANGE_PER_KG` with them).
What it does do is fold in a purity multiplier: the ViT classifier's
`waste_confidence` on each `wastes` row (see `app/api/routes/waste.py`'s
`/waste/submit`) is the one condition/purity signal that actually exists
today, so a cleanly-classified item (well-sorted, unambiguous material)
draws a better range than a low-confidence one. There's no separate
"condition" field to multiply on top of that.
"""

# [points_per_kg_low, points_per_kg_high] by waste category.
_BASE_RANGE_PER_KG: dict[str, tuple[int, int]] = {
    "plastic": (5, 15),
    "paper": (3, 10),
    "glass": (5, 20),
    "metal": (8, 25),
    "battery": (10, 30),
    "organic": (1, 5),
}
_DEFAULT_RANGE_PER_KG = (5, 15)

# Assumed weight when the submitter didn't provide one, so a token can
# still be issued (and drawn) without a scale.
_DEFAULT_WEIGHT_KG = 1.0

# waste_confidence (0..1) is mapped onto this [floor, 1.0] band rather
# than used directly, so even a low-confidence classification still
# yields a usable (if unfavorable) range instead of near-zero points.
_MIN_PURITY_MULTIPLIER = 0.7


def compute_token_range(waste_label: str, weight_kg: float | None, waste_confidence: float) -> tuple[int, int]:
    """Derive a [start_range, end_range] point range for one waste item.

    `waste_confidence` is the classifier's confidence in `waste_label`
    (0..1) and is used as a purity multiplier on the per-kg range.
    """
    low_per_kg, high_per_kg = _BASE_RANGE_PER_KG.get(waste_label.lower(), _DEFAULT_RANGE_PER_KG)
    weight = weight_kg if weight_kg and weight_kg > 0 else _DEFAULT_WEIGHT_KG
    purity = _MIN_PURITY_MULTIPLIER + (1 - _MIN_PURITY_MULTIPLIER) * max(0.0, min(1.0, waste_confidence))
    start_range = max(1, round(low_per_kg * weight * purity))
    end_range = max(start_range, round(high_per_kg * weight * purity))
    return start_range, end_range
