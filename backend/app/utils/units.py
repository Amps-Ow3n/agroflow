"""Agricultural procurement measurement-unit domain rules."""

from __future__ import annotations

import re

SUPPORTED_UNITS = {
    "kg": "mass",
    "g": "mass",
    "tonne": "mass",
    "l": "volume",
    "ml": "volume",
    "piece": "count",
    "unit": "count",
    "dozen": "count",
    "crate": "count",
    "bag": "count",
    "sack": "count",
}

PRODUCT_UNIT_RULES = (
    (re.compile(r"\b(beans?|peas?|lentils?|rice|maize|corn|flour|wheat|millet|sorghum|cassava|potato|sweet potato|groundnut|nuts?)\b", re.I), {"kg", "g", "tonne", "bag", "sack"}),
    (re.compile(r"\b(milk|water|juice|oil|cooking oil|sunflower oil|vegetable oil)\b", re.I), {"l", "ml", "kg"}),
    (re.compile(r"\b(egg|eggs|banana|bananas|mango|mangoes|orange|oranges|bread|loaf|loaves)\b", re.I), {"piece", "unit", "dozen", "crate", "kg", "g"}),
)

DEFAULT_ALLOWED_UNITS = {"kg", "g", "tonne", "piece", "unit", "bag", "sack", "crate", "dozen"}


def normalize_unit(value: str) -> str:
    return value.strip().lower()


def allowed_units_for_product(product_name: str) -> set[str]:
    name = (product_name or "").strip()
    for pattern, units in PRODUCT_UNIT_RULES:
        if pattern.search(name):
            return set(units)
    return set(DEFAULT_ALLOWED_UNITS)


def validate_product_unit(product_name: str, unit: str) -> str:
    normalized = normalize_unit(unit)
    if normalized not in SUPPORTED_UNITS:
        raise ValueError(
            f"Unsupported unit '{unit}'. Choose a supported procurement unit."
        )
    allowed = allowed_units_for_product(product_name)
    if normalized not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(
            f"Unit '{unit}' is not valid for '{product_name}'. Allowed units: {choices}."
        )
    return normalized
