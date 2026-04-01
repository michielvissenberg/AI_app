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
    metrics_source = _extract_metrics_by_label(aggregated_metrics, compressed_payload)
    output["ratios"] = calculate_important_ratios_from_sources(
        aggregated_metrics=metrics_source,
        raw_statement_payload=raw_statement_payload,
    )
    return output


def _extract_metrics_by_label(
    aggregated_metrics: Dict[str, Any],
    compressed_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Returns statement metrics from either explicit input or canonical envelope."""
    if isinstance(aggregated_metrics, dict) and "statement_metrics" in aggregated_metrics:
        nested = aggregated_metrics.get("statement_metrics")
        if isinstance(nested, dict):
            return nested
    if isinstance(aggregated_metrics, dict):
        return aggregated_metrics
    nested = compressed_payload.get("statement_metrics")
    if isinstance(nested, dict):
        return nested
    return {}
