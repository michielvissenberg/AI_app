"""Structure for important financial ratio calculation.

Design:
- Input: resolved field map from field_resolver (strictly validated)
- Output: plain dicts so results can be merged into one large JSON file
"""

from __future__ import annotations

from typing import Any, Dict, List
from models.ratio_definitions import RATIO_DEFINITIONS
from scripts.field_resolver import FieldResolutionError, resolve_fields_for_ratio


def calculate_important_ratios(resolved_fields: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
	"""Calculate important ratios from resolved inputs.

	Returns:
	{
	  "gross_margin": {"value": ..., "unit": "ratio", "inputs": [...]},
	  ...
	}
	"""
	ratios: Dict[str, Dict[str, Any]] = {}

	for ratio_name, definition in RATIO_DEFINITIONS.items():
		required_fields: List[str] = definition["required_fields"]
		inputs = {field: resolved_fields.get(field) for field in required_fields}
		value = _compute_ratio_value(ratio_name, inputs)

		ratios[ratio_name] = {
			"value": value,
			"unit": "ratio",
			"description": definition["description"],
			"inputs": inputs,
		}

	return ratios


def calculate_important_ratios_from_sources(
	aggregated_metrics: Dict[str, Any],
	raw_statement_payload: Dict[str, Any],
	strict_missing_fields: bool = False,
) -> Dict[str, Dict[str, Any]]:
	"""Resolve inputs per-ratio and compute all ratios."""
	ratios: Dict[str, Dict[str, Any]] = {}

	for ratio_name, definition in RATIO_DEFINITIONS.items():
		try:
			inputs = resolve_fields_for_ratio(
				ratio_name=ratio_name,
				aggregated_metrics=aggregated_metrics,
				raw_statement_payload=raw_statement_payload,
			)
			value = _compute_ratio_value(ratio_name, inputs)

			ratios[ratio_name] = {
				"value": value,
				"unit": "ratio",
				"description": definition["description"],
				"inputs": inputs,
				"status": "ok",
			}
		except FieldResolutionError as exc:
			if strict_missing_fields:
				raise

			ratios[ratio_name] = {
				"value": None,
				"unit": "ratio",
				"description": definition["description"],
				"inputs": {},
				"status": "missing_inputs",
				"missing_fields": exc.missing_fields,
				"error": str(exc),
			}

	return ratios


def _compute_ratio_value(ratio_name: str, inputs: Dict[str, float | None]) -> float | None:
	"""Compute one ratio value with safe handling for missing/zero denominators."""

	def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
		if numerator is None or denominator is None or denominator == 0:
			return None
		return numerator / denominator

	match ratio_name:
		case "gross_margin":
			return safe_divide(inputs.get("gross_profit"), inputs.get("revenue"))

		case "operating_margin":
			return safe_divide(inputs.get("operating_income"), inputs.get("revenue"))

		case "net_margin":
			return safe_divide(inputs.get("net_income"), inputs.get("revenue"))

		case "current_ratio":
			return safe_divide(inputs.get("total_current_assets"), inputs.get("total_current_liabilities"))

		case "quick_ratio":
			quick_assets = (
				(inputs.get("cash_and_cash_equivalents") or 0.0)
				+ (inputs.get("marketable_securities") or 0.0)
				+ (inputs.get("accounts_receivable_net") or 0.0)
			)
			has_any_component = any(
				inputs.get(field) is not None
				for field in ["cash_and_cash_equivalents", "marketable_securities", "accounts_receivable_net"]
			)
			if not has_any_component:
				return None
			return safe_divide(quick_assets, inputs.get("total_current_liabilities"))

		case "cash_ratio":
			return safe_divide(inputs.get("cash_and_cash_equivalents"), inputs.get("total_current_liabilities"))

		case "working_capital_to_assets":
			current_assets = inputs.get("total_current_assets")
			current_liabilities = inputs.get("total_current_liabilities")
			if current_assets is None or current_liabilities is None:
				return None
			return safe_divide(current_assets - current_liabilities, inputs.get("total_assets"))

		case "debt_to_equity":
			return safe_divide(inputs.get("total_liabilities"), inputs.get("total_shareholders_equity"))

		case "debt_to_assets":
			return safe_divide(inputs.get("total_liabilities"), inputs.get("total_assets"))

		case "equity_ratio":
			return safe_divide(inputs.get("total_shareholders_equity"), inputs.get("total_assets"))

		case "asset_turnover":
			return safe_divide(inputs.get("revenue"), inputs.get("total_assets"))

		case "return_on_assets":
			return safe_divide(inputs.get("net_income"), inputs.get("total_assets"))

		case "return_on_equity":
			return safe_divide(inputs.get("net_income"), inputs.get("total_shareholders_equity"))

		case "operating_cash_flow_margin":
			return safe_divide(inputs.get("net_cash_from_operating_activities"), inputs.get("revenue"))

		case "operating_cash_flow_to_current_liabilities":
			return safe_divide(inputs.get("net_cash_from_operating_activities"), inputs.get("total_current_liabilities"))

		case "cash_flow_to_debt":
			return safe_divide(inputs.get("net_cash_from_operating_activities"), inputs.get("total_liabilities"))

		case "interest_coverage":
			return safe_divide(inputs.get("operating_income"), inputs.get("interest_expense"))

		case "gross_profit_to_assets":
			return safe_divide(inputs.get("gross_profit"), inputs.get("total_assets"))

		case "operating_return_on_assets":
			return safe_divide(inputs.get("operating_income"), inputs.get("total_assets"))

		case "retained_earnings_to_assets":
			return safe_divide(inputs.get("retained_earnings"), inputs.get("total_assets"))

		case _:
			raise ValueError(f"Unsupported ratio: {ratio_name}")
