import re

from models.normalization_maps import NORMALIZED_LABEL_MAPS, SCALE_TOKEN_MAP


MISSING_MARKERS = {
    "",
    "n/a",
    "na",
    "nm",
    "n.m.",
    "not meaningful",
    "not available",
    "-",
    "—",
    "–",
    "--",
}


SUPPLEMENTAL_SEGMENT_TERMS = {
    "segment",
    "segments",
    "geographic",
    "geography",
    "product",
    "products",
    "region",
    "regional",
    "category",
    "categories",
    "business_unit",
    "channel",
}

def _normalize_raw(raw_value: str) -> str:
    """Normalizes raw cell text to a lowercase trimmed token."""
    return (raw_value or "").strip().lower()


def is_percentage_value(raw_value: str) -> bool:
    """Returns True when the raw value expresses a percentage-like measure."""
    normalized = _normalize_raw(raw_value)
    return "%" in normalized or "percent" in normalized or "pct" in normalized


def _is_missing_value(raw_value: str) -> bool:
    """Determines whether a raw value represents missing or non-meaningful data."""
    normalized = _normalize_raw(raw_value)
    if normalized in MISSING_MARKERS:
        return True

    normalized_compact = re.sub(r"\s+", "", normalized)
    return normalized_compact in {"-", "—", "–", "--", "n/a", "na", "nm"}


def _extract_scale(raw_value: str, is_percent: bool) -> str:
    """Infers numeric scale units (units/thousands/millions/billions/percent) from raw text."""
    if is_percent:
        return "percent"

    normalized = _normalize_raw(raw_value)

    match_word = re.search(r"\b(thousand|thousands|million|millions|billion|billions|mn|mm|bn)\b", normalized)
    if match_word:
        return SCALE_TOKEN_MAP[match_word.group(1)]

    match_suffix = re.search(r"[-+()$€£\s,]?\d[\d,]*(?:\.\d+)?\s*(k|m|b|bn|mm|mn)\b", normalized)
    if match_suffix:
        return SCALE_TOKEN_MAP[match_suffix.group(1)]

    return "units"


def parse_financial_value(raw_value: str):
    """Parses a financial table value into numeric value, unit, scale, and parse status."""
    is_percent = is_percentage_value(raw_value)
    unit = "%" if is_percent else "USD"
    scale = _extract_scale(raw_value, is_percent)

    if _is_missing_value(raw_value):
        return {
            "value": None,
            "parse_status": "missing",
            "unit": unit,
            "scale": scale,
        }

    candidate = (raw_value or "").strip()
    candidate = candidate.replace("−", "-")

    if candidate.startswith("(") and candidate.endswith(")"):
        candidate = "-" + candidate[1:-1]

    candidate = re.sub(r"\b(?:thousand|thousands|million|millions|billion|billions|mn|mm|bn)\b", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"[$€£,%\s,]", "", candidate)
    candidate = re.sub(r"(?<=\d)[kKmMbB]$", "", candidate)

    if candidate in {"", "-", "+", "."}:
        return {
            "value": None,
            "parse_status": "parse_failure",
            "unit": unit,
            "scale": scale,
        }

    try:
        parsed_number = float(candidate)
    except ValueError:
        return {
            "value": None,
            "parse_status": "parse_failure",
            "unit": unit,
            "scale": scale,
        }

    return {
        "value": parsed_number,
        "parse_status": "ok",
        "unit": unit,
        "scale": scale,
    }


def clean_financial_value(raw_value: str):
    """Compatibility wrapper that returns only the parsed numeric value."""
    return parse_financial_value(raw_value)["value"]


def looks_like_supplemental_segment_label(label: str) -> bool:
    """Returns True when a row label appears to be segment/product supplemental detail."""
    normalized = normalize_label(label)
    if not normalized:
        return False

    if normalized in SUPPLEMENTAL_SEGMENT_TERMS:
        return True

    tokens = set(normalized.split("_"))
    if SUPPLEMENTAL_SEGMENT_TERMS.intersection(tokens):
        return True

    if normalized.startswith("net_sales_by_") or normalized.startswith("revenue_by_"):
        return True

    generic_by_prefixes = (
        "sales_by_",
        "by_segment_",
        "segment_",
        "by_product_",
        "product_",
        "by_geography_",
        "geographic_",
        "regional_",
    )
    return normalized.startswith(generic_by_prefixes)
    
def normalize_label(label: str) -> str:
    """
    Standardizes a text label for programmatic use and search indexing.

    Cleaning steps:
    1. Trims leading/trailing whitespace.
    2. Converts all characters to lowercase.
    3. Replaces spaces with underscores.
    4. Removes trailing colons or special characters.

    Example: "Total Revenue: " -> "total_revenue"

    Args:
        label (str): The raw text label from the first column of a table.

    Returns:
        str: A slug-style normalized string.
    """
    normalized = (label or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9\s_&/.-]", "", normalized)
    normalized = normalized.replace(":", "")
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("/", " ")
    normalized = re.sub(r"[\s.-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    for label_map in NORMALIZED_LABEL_MAPS:
        mapped = label_map.get(normalized)
        if mapped is not None:
            return mapped

    return normalized