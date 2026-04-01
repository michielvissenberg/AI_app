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


# Canonical ratio input aliases that are reused across issuers/filings.
CANONICAL_FIELD_ALIASES: Dict[str, tuple[str, ...]] = {
	"accounts_receivable_net": (
		"accounts_receivable",
		"trade_receivables",
		"receivables",
	),
	"marketable_securities": (
		"short_term_investments",
		"available_for_sale_securities",
		"u_s_treasury_and_foreign_government_securities",
		"u_s_treasury_securities",
		"u_s_agency_securities",
		"non_u_s_government_securities",
		"municipal_securities",
		"corporate_debt_securities",
		"asset_backed_securities",
	),
	"net_cash_from_operating_activities": (
		"net_cash_provided_by_operating_activities",
		"net_cash_provided_by_used_in_operating_activities",
	),
	"interest_expense": (
		"interest_and_other_debt_expense_net",
		"interest_expense_net",
		"interest_cost",
		"related_interest_costs",
		"finance_costs",
	),
	"retained_earnings": (
		"retained_earnings_accumulated_deficit",
		"accumulated_earnings",
		"earnings_reinvested_in_the_business",
		"undistributed_earnings",
	),
	"total_shareholders_equity": (
		"total_stockholders_equity",
		"stockholders_equity",
		"total_stockholders_equity_deficit",
		"total_stockholders_equity_deficit_attributable_to_altria",
	),
}


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

	metrics_by_label = _extract_metrics_by_label(aggregated_metrics)

	resolved_map: Dict[str, float] = {}
	missing_fields: List[str] = []

	for field_name in fields:
		resolved = _resolve_single_field(
			field_name=field_name,
			aggregated_metrics=metrics_by_label,
			raw_statement_payload=raw_statement_payload,
		)
		if resolved is None or resolved.value is None:
			missing_fields.append(field_name)
			continue
		resolved_map[field_name] = resolved.value

	if missing_fields:
		raise FieldResolutionError(missing_fields, ratio_name=ratio_name)

	return resolved_map


def _extract_metrics_by_label(payload_or_metrics: Dict[str, Any]) -> Dict[str, Any]:
	"""Returns normalized-label metric map from either envelope or direct map."""
	if not isinstance(payload_or_metrics, dict):
		return {}
	statement_metrics = payload_or_metrics.get("statement_metrics")
	if isinstance(statement_metrics, dict):
		return statement_metrics
	return payload_or_metrics


def _resolve_single_field(
	field_name: str,
	aggregated_metrics: Dict[str, Any],
	raw_statement_payload: Dict[str, Any],
) -> Optional[ResolvedField]:
	"""Resolve a single field using primary+fallback flow."""
	candidate_labels = _candidate_labels(field_name)
	resolved = _resolve_from_aggregated(candidate_labels, aggregated_metrics)
	if resolved is not None and resolved.value is not None:
		return resolved

	return _resolve_from_raw(candidate_labels, raw_statement_payload)


def _resolve_from_aggregated(candidate_labels: Sequence[str], aggregated_metrics: Dict[str, Any]) -> Optional[ResolvedField]:
	"""Primary resolver against aggregated metrics."""
	for label in candidate_labels:
		metric = aggregated_metrics.get(label)
		if metric is None:
			continue

		source_label = _metric_source_label(metric)
		if not _is_semantically_valid_candidate(candidate_labels[0], source_label):
			continue

		if isinstance(metric, dict):
			raw_value = metric.get("value")
		else:
			raw_value = getattr(metric, "value", None)

		value = _coerce_float(raw_value)
		if value is None:
			continue

		source = "aggregated" if label == candidate_labels[0] else "aggregated_alias"
		return ResolvedField(field_name=label, value=value, source=source)

	return None


def _resolve_from_raw(candidate_labels: Sequence[str], raw_statement_payload: Dict[str, Any]) -> Optional[ResolvedField]:
	"""Fallback resolver against raw statement items."""
	label_set = set(candidate_labels)
	candidates = [
		item
		for item in _raw_items(raw_statement_payload)
		if item.get("normalized_label") in label_set
		and _is_semantically_valid_candidate(candidate_labels[0], item.get("label"))
	]
	if not candidates:
		return None

	best_item = max(candidates, key=_raw_candidate_score)
	raw_value = best_item.get("current_period_value")
	if raw_value is None:
		raw_value = best_item.get("value")

	value = _coerce_float(raw_value)
	if value is None:
		return None

	resolved_label = str(best_item.get("normalized_label") or candidate_labels[0])
	source = "raw_fallback" if resolved_label == candidate_labels[0] else "raw_alias_fallback"
	return ResolvedField(field_name=resolved_label, value=value, source=source)


def _candidate_labels(field_name: str) -> List[str]:
	"""Returns canonical field name followed by explicit alias labels."""
	aliases = list(CANONICAL_FIELD_ALIASES.get(field_name, ()))
	return [field_name, *aliases]


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


def _metric_source_label(metric: Any) -> Optional[str]:
	"""Returns source label from dict/dataclass metric payload."""
	if isinstance(metric, dict):
		value = metric.get("source_raw_label") or metric.get("source_label")
		return str(value) if value is not None else None
	value = getattr(metric, "source_raw_label", None) or getattr(metric, "source_label", None)
	return str(value) if value is not None else None


def _is_semantically_valid_candidate(field_name: str, source_label: Optional[str]) -> bool:
	"""Applies lightweight semantic guards for known ambiguous aliases."""
	if field_name != "retained_earnings":
		return True
	if not source_label:
		return True
	normalized = source_label.strip().lower()
	has_retained_phrase = "retained" in normalized and "earning" in normalized
	is_accumulated_deficit_only = "accumulated deficit" in normalized and not has_retained_phrase
	return not is_accumulated_deficit_only

