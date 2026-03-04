from __future__ import annotations

from typing import Any, Dict

from scripts.ratio_calculation import calculate_important_ratios_from_sources


def add_ratios_to_compressed_payload(
    compressed_payload: Dict[str, Any],
    aggregated_metrics: Dict[str, Any],
    raw_statement_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Return compressed payload extended with ratio results."""
    output = dict(compressed_payload)
    output["ratios"] = calculate_important_ratios_from_sources(
        aggregated_metrics=aggregated_metrics,
        raw_statement_payload=raw_statement_payload,
    )
    return output
