import re


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

SCALE_TOKEN_MAP = {
    "k": "thousands",
    "thousand": "thousands",
    "thousands": "thousands",
    "m": "millions",
    "mm": "millions",
    "mn": "millions",
    "million": "millions",
    "millions": "millions",
    "b": "billions",
    "bn": "billions",
    "billion": "billions",
    "billions": "billions",
}


def _normalize_raw(raw_value: str) -> str:
    return (raw_value or "").strip().lower()

def is_percentage_value(raw_value: str) -> bool:
    normalized = _normalize_raw(raw_value)
    return "%" in normalized or "percent" in normalized or "pct" in normalized


def _is_missing_value(raw_value: str) -> bool:
    normalized = _normalize_raw(raw_value)
    if normalized in MISSING_MARKERS:
        return True

    normalized_compact = re.sub(r"\s+", "", normalized)
    return normalized_compact in {"-", "—", "–", "--", "n/a", "na", "nm"}


def _extract_scale(raw_value: str, is_percent: bool) -> str:
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
    return parse_financial_value(raw_value)["value"]
    
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
    return label.strip().lower().replace(" ", "_").replace(":", "")