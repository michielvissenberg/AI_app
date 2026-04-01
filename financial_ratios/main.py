import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from models.models import (
	CompanyContext,
	CompanyRecord,
	FilingContext,
	Provenance,
	build_market_metrics_stubs,
)
from models.validation import validate_enriched_record
from scripts.aggregator import aggregate_statement_items_with_diagnostics
from scripts.ratio_enricher import add_ratios_to_compressed_payload


def _to_jsonable(data):
	"""Recursively converts dataclasses and nested structures to JSON-serializable format."""
	if is_dataclass(data):
		return asdict(data)
	if isinstance(data, dict):
		return {str(key): _to_jsonable(value) for key, value in data.items()}
	if isinstance(data, list):
		return [_to_jsonable(item) for item in data]
	return data


def parse_args() -> argparse.Namespace:
	"""Parses CLI arguments for the statement aggregation and ratio computation pipeline."""
	parser = argparse.ArgumentParser(description="Aggregate statement JSON into compressed JSON.")
	parser.add_argument("input_path", help="Path to the input statement JSON file.")
	parser.add_argument(
		"--evaluation",
		help="Optional path to evaluation JSON used to populate provenance KPI fields.",
		default=None,
	)
	return parser.parse_args()


def _require_str(payload: dict, key: str) -> str:
	"""Returns a required string field from payload or raises a clear error."""
	value = payload.get(key)
	if not isinstance(value, str) or not value.strip():
		raise ValueError(f"Missing required non-empty string field: {key}")
	return value


def _derive_fiscal_year(period_ending: str) -> int:
	"""Derives fiscal year from an ISO period ending date."""
	return datetime.strptime(period_ending, "%Y-%m-%d").year


def _derive_fiscal_period(report_type: str, period_ending: str) -> str:
	"""Derives fiscal period with best effort and unknown fallback."""
	if report_type == "10-K":
		return "annual"
	if report_type != "10-Q":
		return "unknown"

	try:
		month = datetime.strptime(period_ending, "%Y-%m-%d").month
	except ValueError:
		return "unknown"

	quarter = (month - 1) // 3 + 1
	if quarter in (1, 2, 3):
		return f"Q{quarter}"
	return "unknown"


def _build_company_record(
	raw_statement_payload: dict,
	aggregated_metrics: dict,
	provenance: Provenance,
) -> CompanyRecord:
	"""Builds the Stage B Workstream 1 canonical envelope around statement metrics."""
	ticker = _require_str(raw_statement_payload, "ticker")
	company_name = _require_str(raw_statement_payload, "company_name")
	report_type = _require_str(raw_statement_payload, "report_type")
	period_ending = _require_str(raw_statement_payload, "period_ending")

	company_context = CompanyContext(
		ticker=ticker,
		company_name=company_name,
	)
	filing_context = FilingContext(
		report_type=report_type,
		period_ending=period_ending,
		fiscal_year=_derive_fiscal_year(period_ending),
		fiscal_period=_derive_fiscal_period(report_type, period_ending),
		source_pdf=raw_statement_payload.get("source_pdf") if isinstance(raw_statement_payload.get("source_pdf"), str) else None,
	)

	return CompanyRecord(
		schema_version="1.0",
		company_context=company_context,
		filing_context=filing_context,
		statement_metrics=aggregated_metrics,
		market_metrics=build_market_metrics_stubs(),
		ratios={},
		provenance=provenance,
	)


def _load_optional_json(path_value: Optional[str]) -> Optional[Dict[str, Any]]:
	"""Loads JSON from disk when a path is provided; returns None when omitted."""
	if not path_value:
		return None
	path = Path(path_value)
	return json.loads(path.read_text(encoding="utf-8"))


def _as_float_or_none(value: Any) -> Optional[float]:
	"""Safely coerces a numeric value to float."""
	if value is None:
		return None
	try:
		return float(value)
	except (TypeError, ValueError):
		return None


def _get_evaluation_metrics(evaluation_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
	"""Extracts KPI and verdict fields from the optional evaluation artifact."""
	if not evaluation_payload:
		return {
			"statement_detection_accuracy": None,
			"line_item_mapping_accuracy": None,
			"numeric_parse_accuracy": None,
			"evaluation_verdict": "not_run",
		}

	measured = evaluation_payload.get("kpis", {}).get("measured", {})
	verdict = evaluation_payload.get("gate", {}).get("verdict")
	if verdict not in {"pass", "fail"}:
		verdict = "not_run"

	return {
		"statement_detection_accuracy": _as_float_or_none(measured.get("statement_detection_accuracy")),
		"line_item_mapping_accuracy": _as_float_or_none(measured.get("line_item_mapping_accuracy")),
		"numeric_parse_accuracy": _as_float_or_none(measured.get("numeric_parse_accuracy")),
		"evaluation_verdict": verdict,
	}


def _count_duplicate_collisions_resolved(duplicate_diagnostics: Dict[str, Any]) -> int:
	"""Counts how many duplicate candidate rows were resolved away."""
	collisions = duplicate_diagnostics.get("collisions", [])
	if not isinstance(collisions, list):
		return 0
	resolved = 0
	for collision in collisions:
		if not isinstance(collision, dict):
			continue
		count = collision.get("collision_count")
		if isinstance(count, int) and count > 1:
			resolved += count - 1
	return resolved


def _build_provenance(
	raw_statement_payload: Dict[str, Any],
	duplicate_diagnostics: Dict[str, Any],
	evaluation_payload: Optional[Dict[str, Any]],
	aggregated_at: str,
) -> Provenance:
	"""Builds a fully populated Workstream 3 provenance object."""
	eval_metrics = _get_evaluation_metrics(evaluation_payload)

	extraction_engine = raw_statement_payload.get("extraction_engine")
	if not isinstance(extraction_engine, str) or not extraction_engine.strip():
		extraction_engine = "unknown"

	extracted_at = raw_statement_payload.get("extracted_at")
	if not isinstance(extracted_at, str) or not extracted_at.strip():
		extracted_at = None

	source_pdf = raw_statement_payload.get("source_pdf")
	if not isinstance(source_pdf, str) or not source_pdf.strip():
		source_pdf = None

	return Provenance(
		run_id=str(uuid4()),
		pipeline_version="0.1.0",
		extraction_engine=extraction_engine,
		extracted_at=extracted_at,
		aggregated_at=aggregated_at,
		source_pdf=source_pdf,
		statement_detection_accuracy=eval_metrics["statement_detection_accuracy"],
		line_item_mapping_accuracy=eval_metrics["line_item_mapping_accuracy"],
		numeric_parse_accuracy=eval_metrics["numeric_parse_accuracy"],
		evaluation_verdict=eval_metrics["evaluation_verdict"],
		duplicate_collisions_resolved=_count_duplicate_collisions_resolved(duplicate_diagnostics),
	)


def main() -> int:
	"""Aggregates statement items, computes financial ratios, and exports compressed payload with diagnostics."""
	args = parse_args()
	input_path = Path(args.input_path)
	aggregated_at = datetime.now(timezone.utc).isoformat()
	raw_statement_payload = json.loads(input_path.read_text(encoding="utf-8"))
	evaluation_payload = _load_optional_json(args.evaluation)

	aggregated, duplicate_diagnostics = aggregate_statement_items_with_diagnostics(input_path)
	provenance = _build_provenance(
		raw_statement_payload=raw_statement_payload,
		duplicate_diagnostics=duplicate_diagnostics,
		evaluation_payload=evaluation_payload,
		aggregated_at=aggregated_at,
	)
	canonical_record = _build_company_record(
		raw_statement_payload=raw_statement_payload,
		aggregated_metrics=aggregated,
		provenance=provenance,
	)
	compressed_payload = _to_jsonable(canonical_record)
	output_payload = add_ratios_to_compressed_payload(
		compressed_payload=compressed_payload,
		aggregated_metrics=aggregated,
		raw_statement_payload=raw_statement_payload,
	)

	validation_violations = validate_enriched_record(output_payload)
	for violation in validation_violations:
		print(f"WARNING: schema validation violation: {violation}")

	output_dir = Path(__file__).resolve().parents[1] / "data_compressed"
	output_dir.mkdir(parents=True, exist_ok=True)
	output_path = output_dir / f"{input_path.stem}.json"
	diagnostics_path = output_dir / f"{input_path.stem}_duplicate_diagnostics.json"

	with open(output_path, "w", encoding="utf-8") as handle:
		json.dump(output_payload, handle, indent=2)

	with open(diagnostics_path, "w", encoding="utf-8") as handle:
		json.dump(_to_jsonable(duplicate_diagnostics), handle, indent=2)

	return 0


if __name__ == "__main__":
	raise SystemExit(main())

