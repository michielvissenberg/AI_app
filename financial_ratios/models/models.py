from dataclasses import dataclass
from typing import Any, Dict, List, Optional


MARKET_METRIC_NOT_FETCHED_STUB: Dict[str, Any] = {
	"value": None,
	"unit": None,
	"source_status": "not_fetched",
}

ALLOWED_METRIC_STATUSES = {"ok", "missing", "ambiguous", "parse_error"}
ALLOWED_MARKET_SOURCE_STATUSES = {"not_fetched"}


def build_market_metrics_stubs() -> Dict[str, Dict[str, Any]]:
	"""Returns Stage B market metric placeholders for Stage C enrichment."""
	fields = ["share_price", "shares_outstanding", "market_cap", "total_debt", "enterprise_value"]
	return {field: dict(MARKET_METRIC_NOT_FETCHED_STUB) for field in fields}

@dataclass
class AggregatedMetric:
	normalized_label: str
	value: Optional[float]
	priorValue: Optional[float]
	status: str = "ok"
	unit: Optional[str] = None
	source_label: Optional[str] = None
	statement_type: Optional[str] = None
	yoy_change: Optional[float] = None
	yoy_unit: Optional[str] = None
	scale: Optional[str] = None
	statement_type_confidence: Optional[str] = None
	source_raw_label: Optional[str] = None


@dataclass
class CompanyContext:
	ticker: str
	company_name: str
	currency: str = "USD"


@dataclass
class FilingContext:
	report_type: str
	period_ending: str
	fiscal_year: int
	fiscal_period: str
	source_pdf: Optional[str] = None


@dataclass
class Provenance:
	run_id: str
	pipeline_version: str
	extraction_engine: str
	extracted_at: Optional[str]
	aggregated_at: str
	source_pdf: Optional[str]
	statement_detection_accuracy: Optional[float] = None
	line_item_mapping_accuracy: Optional[float] = None
	numeric_parse_accuracy: Optional[float] = None
	evaluation_verdict: str = "not_run"
	duplicate_collisions_resolved: int = 0


@dataclass
class CompanyRecord:
	schema_version: str
	company_context: CompanyContext
	filing_context: FilingContext
	statement_metrics: Dict[str, AggregatedMetric]
	market_metrics: Dict[str, Dict[str, Any]]
	ratios: Dict[str, Dict[str, Any]]
	provenance: Provenance


def validate_status_tags(record: Dict[str, Any]) -> List[str]:
	"""Validates metric and market status tags and returns human-readable violations."""
	violations: List[str] = []

	statement_metrics = record.get("statement_metrics", {})
	if isinstance(statement_metrics, dict):
		for metric_name, metric in statement_metrics.items():
			if not isinstance(metric, dict):
				continue
			status = metric.get("status")
			if status not in ALLOWED_METRIC_STATUSES:
				violations.append(
					f"statement_metrics.{metric_name}.status invalid: {status!r}; expected one of {sorted(ALLOWED_METRIC_STATUSES)}"
				)

	market_metrics = record.get("market_metrics", {})
	if isinstance(market_metrics, dict):
		for field_name, field_payload in market_metrics.items():
			if not isinstance(field_payload, dict):
				continue
			source_status = field_payload.get("source_status")
			if source_status not in ALLOWED_MARKET_SOURCE_STATUSES:
				violations.append(
					f"market_metrics.{field_name}.source_status invalid: {source_status!r}; expected one of {sorted(ALLOWED_MARKET_SOURCE_STATUSES)}"
				)

	return violations
