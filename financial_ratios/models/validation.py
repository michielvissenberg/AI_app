from __future__ import annotations

from typing import Any, Dict, List, Set

from models.models import validate_status_tags


ALLOWED_UNITS: Set[str] = {
	"USD",
	"%",
	"ratio",
	"shares",
	"millions",
	"thousands",
	"units",
}


def validate_enriched_record(record: Dict[str, Any]) -> List[str]:
	"""Validates the Stage B enriched payload and returns violations."""
	violations: List[str] = []

	required_sections = [
		"company_context",
		"filing_context",
		"statement_metrics",
		"ratios",
		"provenance",
	]
	for section_name in required_sections:
		if section_name not in record:
			violations.append(f"Missing required top-level section: {section_name}")

	if "schema_version" not in record:
		violations.append("Missing required top-level key: schema_version")

	violations.extend(_validate_required_context_fields(record))
	violations.extend(_validate_metric_units(record))
	violations.extend(validate_status_tags(record))

	return violations


def _validate_required_context_fields(record: Dict[str, Any]) -> List[str]:
	violations: List[str] = []

	company_context = record.get("company_context")
	if isinstance(company_context, dict):
		for field in ["ticker", "company_name"]:
			if company_context.get(field) in (None, ""):
				violations.append(f"company_context.{field} is required and must be non-null")
	else:
		violations.append("company_context must be an object")

	filing_context = record.get("filing_context")
	if isinstance(filing_context, dict):
		for field in ["report_type", "period_ending", "fiscal_year", "fiscal_period"]:
			if filing_context.get(field) in (None, ""):
				violations.append(f"filing_context.{field} is required and must be non-null")
	else:
		violations.append("filing_context must be an object")

	provenance = record.get("provenance")
	if isinstance(provenance, dict):
		for field in ["run_id", "pipeline_version", "aggregated_at", "evaluation_verdict"]:
			if provenance.get(field) in (None, ""):
				violations.append(f"provenance.{field} is required and must be non-null")
	else:
		violations.append("provenance must be an object")

	return violations


def _validate_metric_units(record: Dict[str, Any]) -> List[str]:
	violations: List[str] = []

	statement_metrics = record.get("statement_metrics")
	if isinstance(statement_metrics, dict):
		for metric_name, metric in statement_metrics.items():
			if not isinstance(metric, dict):
				continue
			unit = metric.get("unit")
			if unit is None:
				continue
			if unit not in ALLOWED_UNITS:
				violations.append(
					f"statement_metrics.{metric_name}.unit invalid: {unit!r}; expected one of {sorted(ALLOWED_UNITS)}"
				)

	ratios = record.get("ratios")
	if isinstance(ratios, dict):
		for ratio_name, ratio in ratios.items():
			if not isinstance(ratio, dict):
				continue
			unit = ratio.get("unit")
			if unit is None:
				continue
			if unit not in ALLOWED_UNITS:
				violations.append(
					f"ratios.{ratio_name}.unit invalid: {unit!r}; expected one of {sorted(ALLOWED_UNITS)}"
				)

	market_metrics = record.get("market_metrics")
	if isinstance(market_metrics, dict):
		for field_name, field_payload in market_metrics.items():
			if not isinstance(field_payload, dict):
				continue
			unit = field_payload.get("unit")
			if unit is None:
				continue
			if unit not in ALLOWED_UNITS:
				violations.append(
					f"market_metrics.{field_name}.unit invalid: {unit!r}; expected one of {sorted(ALLOWED_UNITS)}"
				)

	return violations
