"""Aggregation scaffold for statement JSON data.

Goal:
- Load raw statement JSON
- Group rows by `normalized_label`
- Remove duplicates / pick best candidate values
- Return a clean dictionary for ratio calculations

"""
from pathlib import Path
from typing import Any, Dict, List, Tuple
from models.models import AggregatedMetric
from collections import defaultdict

import json

PREFERRED_STATEMENT_TYPE_BY_LABEL = {
    "revenue": "income_statement",
    "gross_profit": "income_statement",
    "operating_income": "income_statement",
    "net_income": "income_statement",
    "total_assets": "balance_sheet",
    "total_liabilities": "balance_sheet",
    "total_current_assets": "balance_sheet",
    "total_current_liabilities": "balance_sheet",
    "cash_and_cash_equivalents": "balance_sheet",
    "accounts_receivable_net": "balance_sheet",
    "marketable_securities": "balance_sheet",
    "total_shareholders_equity": "balance_sheet",
    "net_cash_from_operating_activities": "cash_flow_statement",
    "net_cash_from_investing_activities": "cash_flow_statement",
    "net_cash_from_financing_activities": "cash_flow_statement",
}


CRITICAL_KPI_ANCHORS = {"revenue", "net_income", "total_assets"}

def aggregate_statement_items(statement_json_path: Path) -> Dict[str, AggregatedMetric]:
    """Main entrypoint used by callers.
    Expected flow:
    1) load statement payload
    2) group items by normalized label
    3) resolve duplicates per label
    4) return compact metric map keyed by normalized_label
    """
    payload = _load_statement_json(statement_json_path)
    items = _get_items(payload)
    items = _clean_items(items)
    grouped = _group_by_normalized_label(items)
    resolved, _ = _resolve_duplicates(grouped)
    return resolved


def aggregate_statement_items_with_diagnostics(
    statement_json_path: Path,
) -> Tuple[Dict[str, AggregatedMetric], Dict[str, Any]]:
    """Aggregates statement items and returns duplicate resolution diagnostics."""
    payload = _load_statement_json(statement_json_path)
    items = _get_items(payload)
    items = _clean_items(items)
    grouped = _group_by_normalized_label(items)
    resolved, duplicate_diagnostics = _resolve_duplicates(grouped)
    return resolved, duplicate_diagnostics

def _load_statement_json(path: Path) -> Dict[str, Any]:
    """Load and parse the statement JSON file."""
    return json.loads(path.read_text()) if path.exists() else {}
    
def _get_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract the `items` list from payload with basic validation."""
    return payload.get('items', [])

def _group_by_normalized_label(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group raw rows by normalized label."""
    grouped_data = defaultdict(list)
    for item in items:
        normalized_label = item.get("normalized_label")
        grouped_data[normalized_label].append(item)
    return grouped_data

def _resolve_duplicates(
    grouped_items: Dict[str, List[Dict[str, Any]]]
) -> Tuple[Dict[str, AggregatedMetric], Dict[str, Any]]:
    """Select one canonical item per label and build AggregatedMetric objects."""
    resolved = {}
    collisions: List[Dict[str, Any]] = []
    for label, entries in grouped_items.items():
        if len(entries) == 1:
            best_item = entries[0]
            rejected_items: List[Dict[str, Any]] = []
        else:
            best_item = _pick_best_duplicate(entries, label)
            rejected_items = [entry for entry in entries if entry is not best_item]

        selected_value = best_item.get("current_period_value")
        if selected_value is None:
            selected_value = best_item.get("value")

        resolved[label] = AggregatedMetric(
            normalized_label=label,
            value=selected_value,
            priorValue=best_item.get("prior_period_value"),
            unit=best_item.get("unit"),
            source_label=best_item.get("label"),
            statement_type=best_item.get("statement_type")
        )

        if len(entries) > 1:
            collisions.append(
                {
                    "normalized_label": label,
                    "collision_count": len(entries),
                    "winner": {
                        "source_label": best_item.get("label"),
                        "statement_type": best_item.get("statement_type"),
                        "statement_type_confidence": best_item.get("statement_type_confidence"),
                        "period_alignment_confidence": best_item.get("period_alignment_confidence"),
                        "period_alignment_warning": best_item.get("period_alignment_warning"),
                        "parse_status": best_item.get("parse_status"),
                        "current_period_value": best_item.get("current_period_value"),
                        "prior_period_value": best_item.get("prior_period_value"),
                    },
                    "rejected_candidates": [
                        {
                            "source_label": item.get("label"),
                            "statement_type": item.get("statement_type"),
                            "statement_type_confidence": item.get("statement_type_confidence"),
                            "period_alignment_confidence": item.get("period_alignment_confidence"),
                            "period_alignment_warning": item.get("period_alignment_warning"),
                            "parse_status": item.get("parse_status"),
                            "current_period_value": item.get("current_period_value"),
                            "prior_period_value": item.get("prior_period_value"),
                        }
                        for item in rejected_items
                    ],
                }
            )

    diagnostics = {
        "collision_groups": len(collisions),
        "collisions": collisions,
    }

    return resolved, diagnostics


def _pick_best_duplicate(entries: List[Dict[str, Any]], normalized_label: str) -> Dict[str, Any]:
    preferred_statement_type = PREFERRED_STATEMENT_TYPE_BY_LABEL.get(normalized_label)
    candidate_entries = entries

    if normalized_label in CRITICAL_KPI_ANCHORS:
        high_confidence_entries = [
            item
            for item in entries
            if str(item.get("statement_type_confidence", "")) == "high"
            and str(item.get("period_alignment_confidence", "")) == "high"
            and str(item.get("parse_status", "")).lower() != "ambiguous"
        ]
        if high_confidence_entries:
            candidate_entries = high_confidence_entries

    def score(item: Dict[str, Any]) -> tuple[int, int, int, int, float]:
        points = 0

        parse_status = str(item.get("parse_status", "")).lower()
        if parse_status == "ok":
            points += 4
        elif parse_status in {"ambiguous", "parse_error"}:
            points -= 2

        has_current_period_value = item.get("current_period_value") is not None
        has_prior_period_value = item.get("prior_period_value") is not None
        if has_current_period_value:
            points += 5
        if has_prior_period_value:
            points += 2

        statement_type = item.get("statement_type")
        if statement_type:
            points += 1

        preferred_match_rank = 1
        if preferred_statement_type and statement_type == preferred_statement_type:
            points += 8
        elif preferred_statement_type and statement_type != preferred_statement_type:
            points -= 8
            preferred_match_rank = 0

        selected_value = item.get("current_period_value")
        if selected_value is None:
            selected_value = item.get("value")
        magnitude = abs(float(selected_value)) if selected_value not in (None, "") else 0.0

        return preferred_match_rank, points, int(has_current_period_value), int(has_prior_period_value), magnitude

    return max(candidate_entries, key=score)

def _clean_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """remove noise entries in the data"""
    return [
        item for item in items 
        if not _is_noise(item)
    ]

def _is_noise(item: Dict[str, Any]) -> bool:
    label = str(item.get('normalized_label', ''))
    unit = str(item.get('unit', '')).upper()
    noise_keywords = ['thereafter', 'rsus_', 'common_stock_outstanding', 's&p_500', 'index', 'dow_jones', 'amortized', 'imputed', 'accounting_fair_value', 'less_', '/s/']
    
    if item.get('value') is None: return True
    if label.isdigit(): return True
    if any(word in label for word in noise_keywords): return True
    if label in ['total', 'basic', 'diluted']: return True

    return False
