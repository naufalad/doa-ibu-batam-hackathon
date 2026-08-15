"""Point-range policy for waste tokens.

TODO: this is a placeholder, same spirit as the old flat
`POINTS_PER_OBJECT` constant it replaces in `app/api/routes/waste.py` —
replace with real product rules (market rate per kg per material,
condition/purity multipliers, etc.) once they're defined. For now it just
gives every category a plausible [low, high] point range per kg so a
token draw (`POST /waste/tokens/{id}/draw`) isn't fixed/predictable.
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


def compute_token_range(waste_label: str, weight_kg: float | None) -> tuple[int, int]:
    """Derive a [start_range, end_range] point range for one waste item."""
    low_per_kg, high_per_kg = _BASE_RANGE_PER_KG.get(waste_label.lower(), _DEFAULT_RANGE_PER_KG)
    weight = weight_kg if weight_kg and weight_kg > 0 else _DEFAULT_WEIGHT_KG
    start_range = max(1, round(low_per_kg * weight))
    end_range = max(start_range, round(high_per_kg * weight))
    return start_range, end_range
