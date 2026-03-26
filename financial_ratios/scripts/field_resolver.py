"""Resolve required financial fields for ratio calculation.

Design:
- Primary source: aggregated metrics (clean, canonical)
- Fallback source: raw statement payload (higher recall)
- Missing required fields: raise error

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from models.ratio_definitions import RATIO_DEFINITIONS


class FieldResolutionError(Exception):
	"""Raised when one or more required fields cannot be resolved."""

	def __init__(self, missing_fields: Sequence[str], ratio_name: Optional[str] = None):
		self.missing_fields = list(missing_fields)
		self.ratio_name = ratio_name
		ratio_scope = f" for ratio '{ratio_name}'" if ratio_name else ""
		message = f"Unable to resolve required fields{ratio_scope}: {', '.join(self.missing_fields)}"
		super().__init__(message)


@dataclass
class ResolvedField:
	field_name: str
	value: Optional[float]
	source: str


def resolve_fields_for_ratio(
	ratio_name: str,
	aggregated_metrics: Dict[str, Any],
	raw_statement_payload: Dict[str, Any],
	ratio_definitions: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, float]:
	"""Resolve only the fields needed for one ratio.

	This uses aggregated-first lookup with raw-statement fallback and raises
	FieldResolutionError when required fields for the specific ratio are missing.
	"""
	definitions = ratio_definitions or RATIO_DEFINITIONS
	definition = definitions.get(ratio_name)
	if definition is None:
		raise ValueError(f"Unknown ratio definition: {ratio_name}")

	fields = list(definition.get("required_fields", []))
	if not fields:
		return {}

	resolved_map: Dict[str, float] = {}
	missing_fields: List[str] = []

	for field_name in fields:
		resolved = _resolve_single_field(
			field_name=field_name,
			aggregated_metrics=aggregated_metrics,
			raw_statement_payload=raw_statement_payload,
		)
		if resolved is None or resolved.value is None:
			missing_fields.append(field_name)
			continue
		resolved_map[field_name] = resolved.value

	if missing_fields:
		raise FieldResolutionError(missing_fields, ratio_name=ratio_name)

	return resolved_map


def _resolve_single_field(
	field_name: str,
	aggregated_metrics: Dict[str, Any],
	raw_statement_payload: Dict[str, Any],
) -> Optional[ResolvedField]:
	"""Resolve a single field using primary+fallback flow."""
	resolved = _resolve_from_aggregated(field_name, aggregated_metrics)
	if resolved is not None and resolved.value is not None:
		return resolved

	return _resolve_from_raw(field_name, raw_statement_payload)


def _resolve_from_aggregated(field_name: str, aggregated_metrics: Dict[str, Any]) -> Optional[ResolvedField]:
	"""Primary resolver against aggregated metrics."""
	metric = aggregated_metrics.get(field_name)
	if metric is None:
		return None

	if isinstance(metric, dict):
		raw_value = metric.get("value")
	else:
		raw_value = getattr(metric, "value", None)

	value = _coerce_float(raw_value)
	if value is None:
		return None

	return ResolvedField(field_name=field_name, value=value, source="aggregated")


def _resolve_from_raw(field_name: str, raw_statement_payload: Dict[str, Any]) -> Optional[ResolvedField]:
	"""Fallback resolver against raw statement items."""
	candidates = [item for item in _raw_items(raw_statement_payload) if item.get("normalized_label") == field_name]
	if not candidates:
		return None

	best_item = max(candidates, key=_raw_candidate_score)
	raw_value = best_item.get("current_period_value")
	if raw_value is None:
		raw_value = best_item.get("value")

	value = _coerce_float(raw_value)
	if value is None:
		return None

	return ResolvedField(field_name=field_name, value=value, source="raw_fallback")


def _raw_items(raw_statement_payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
	"""Extract raw item rows safely from statement payload."""
	items = raw_statement_payload.get("items", [])
	return items if isinstance(items, list) else []


def _raw_candidate_score(item: Dict[str, Any]) -> tuple[int, int, float]:
	"""Scores raw fallback candidates to prefer reliable current-period metric rows."""
	points = 0

	if str(item.get("parse_status", "")).lower() == "ok":
		points += 3

	has_current_period = item.get("current_period_value") is not None
	if has_current_period:
		points += 4

	if item.get("statement_type"):
		points += 1

	raw_value = item.get("current_period_value")
	if raw_value is None:
		raw_value = item.get("value")
	value = _coerce_float(raw_value)
	magnitude = abs(value) if value is not None else 0.0

	return points, int(has_current_period), magnitude


def _coerce_float(value: Any) -> Optional[float]:
	"""Safely coerces a value to float, returning None when conversion fails."""
	if value is None:
		return None
	try:
		return float(value)
	except (TypeError, ValueError):
		return None

