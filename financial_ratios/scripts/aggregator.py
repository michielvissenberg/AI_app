"""Aggregation scaffold for statement JSON data.

Goal:
- Load raw statement JSON
- Group rows by `normalized_label`
- Remove duplicates / pick best candidate values
- Return a clean dictionary for ratio calculations

"""
# later wil ik er ook voor zorgen dat de yoy change en misschien ook de kolommen met data meekomen !!!!!!!
from pathlib import Path
from typing import Any, Dict, List
from models.models import AggregatedMetric
from collections import defaultdict

import json

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
    resolved = _resolve_duplicates(grouped)
    return resolved

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

def _resolve_duplicates(grouped_items: Dict[str, List[Dict[str, Any]]]) -> Dict[str, AggregatedMetric]:
    """Select one canonical item per label and build AggregatedMetric objects."""
    resolved = {}
    for label, entries in grouped_items.items():
        if len(entries) == 1:
            best_item = entries[0]
        else:
            best_item = max(entries, key=lambda x: x.get("value", 0) or 0)
        resolved[label] = AggregatedMetric(
            normalized_label=label,
            value=best_item.get("value"),
            priorValue=best_item.get("prior_period_value"),
            unit=best_item.get("unit"),
            source_label=best_item.get("label"),
            statement_type=best_item.get("statement_type")
        )
    return resolved

def _clean_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """remove noise entries in the data"""
    return [
        item for item in items 
        if not _is_noise(item)
    ]

def _is_noise(item: Dict[str, Any]) -> bool:
    label = str(item.get('normalized_label', ''))
    unit = str(item.get('unit', '')).upper()
    noise_keywords = ['thereafter', 'rsus_', 'common_stock_outstanding', 's&p_500', 'index', 'dow_jones', 'amortized', 'imputed', 'accounting_fair_value', 'less_']
    
#    if item.get('value') is None: return True
    if label.startswith('/s/'): return True
    if label.isdigit() and len(label) == 4: return True
    if any(word in label for word in noise_keywords): return True
    if label in ['total', 'basic', 'diluted']: return True

    return False
