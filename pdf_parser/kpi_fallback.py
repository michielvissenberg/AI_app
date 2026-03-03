import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pypdfium2 as pdfium

from models.schemas import FinancialStatement
from main import export


METRIC_SPECS = {
    "monthly_active_users": r"monthly\s+active\s+users?",
    "daily_active_users": r"daily\s+active\s+users?",
    "paid_subscribers": r"paid\s+subscribers",
}


def _extract_page_lines(pdf_path: Path, page_number: int) -> List[str]:
    document = pdfium.PdfDocument(str(pdf_path))
    page_index = page_number - 1
    if page_index < 0 or page_index >= len(document):
        raise ValueError(f"Requested page {page_number} is outside PDF bounds.")

    lines: List[str] = []
    page = document.get_page(page_index)
    text_page = page.get_textpage()
    raw_text = text_page.get_text_range() or ""
    text_page.close()
    page.close()

    for raw_line in raw_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            lines.append(line)

    return lines


def _infer_scale(lines: List[str]) -> str:
    for line in lines:
        lowered = line.lower()
        if "(in millions)" in lowered or "in millions" in lowered:
            return "millions"
        if "(in thousands)" in lowered or "in thousands" in lowered:
            return "thousands"
        if "(in billions)" in lowered or "in billions" in lowered:
            return "billions"
    return "units"


def _extract_two_values(text: str) -> Optional[Tuple[float, float]]:
    tokens = re.findall(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b", text)
    values: List[float] = []

    for token in tokens:
        cleaned = token.replace(",", "")
        if re.fullmatch(r"(?:19|20)\d{2}", cleaned):
            continue
        values.append(float(cleaned))

    if len(values) < 2:
        return None

    return values[0], values[1]


def _find_metric_values(lines: List[str], metric_pattern: str) -> Optional[Tuple[float, float, str]]:
    for idx, line in enumerate(lines):
        if not re.search(metric_pattern, line, flags=re.IGNORECASE):
            continue

        same_line_values = _extract_two_values(line)
        if same_line_values is not None:
            return same_line_values[0], same_line_values[1], line

        if idx + 1 < len(lines):
            merged = f"{line} {lines[idx + 1]}"
            merged_values = _extract_two_values(merged)
            if merged_values is not None:
                return merged_values[0], merged_values[1], line

    return None


def _build_kpi_item(
    normalized_label: str,
    raw_label: str,
    current_value: float,
    prior_value: Optional[float],
    scale: str,
    current_period_label: str,
    prior_period_label: Optional[str],
) -> Dict[str, object]:
    yoy_change = None
    yoy_unit = None
    if prior_value not in (None, 0):
        yoy_change = ((current_value - prior_value) / abs(prior_value)) * 100
        yoy_unit = "%"

    column_values = [current_value] + ([prior_value] if prior_value is not None else [])
    column_units = ["count"] * len(column_values)
    column_scales = [scale] * len(column_values)
    column_parse_statuses = ["ok"] * len(column_values)

    return {
        "label": raw_label,
        "normalized_label": normalized_label,
        "statement_type": None,
        "value": current_value,
        "unit": "count",
        "scale": scale,
        "column_values": column_values,
        "column_units": column_units,
        "column_scales": column_scales,
        "column_parse_statuses": column_parse_statuses,
        "parse_status": "ok",
        "yoy_change": yoy_change,
        "yoy_unit": yoy_unit,
        "current_period_value": current_value,
        "prior_period_value": prior_value,
        "current_period_label": current_period_label,
        "prior_period_label": prior_period_label,
        "current_period_column": 1,
        "prior_period_column": 2 if prior_value is not None else None,
        "supplemental_metrics": None,
    }


def run_kpi_fallback(
    pdf_path: Path,
    statement_json_path: Path,
    output_dir: Optional[Path] = None,
    source_page: int = 61,
) -> int:
    with open(statement_json_path, "r", encoding="utf-8") as handle:
        statement_payload = json.load(handle)

    statement = FinancialStatement.model_validate(statement_payload)
    period_year = int(statement.period_ending[:4])
    lines = _extract_page_lines(pdf_path, page_number=source_page)
    scale = _infer_scale(lines)

    additions = []

    base_items = [
        item
        for item in statement.model_dump(mode="json")["items"]
        if (item.get("normalized_label") or "") not in METRIC_SPECS
    ]

    for normalized_label, metric_pattern in METRIC_SPECS.items():
        extracted = _find_metric_values(lines, metric_pattern)
        if extracted is None:
            continue

        current_value, prior_value, raw_label = extracted
        additions.append(
            _build_kpi_item(
                normalized_label=normalized_label,
                raw_label=raw_label,
                current_value=current_value,
                prior_value=prior_value,
                scale=scale,
                current_period_label=str(period_year),
                prior_period_label=str(period_year - 1),
            )
        )

    if not additions:
        print(f"No KPI metrics found on page {source_page}.")
        return 0

    merged_payload = statement.model_dump(mode="json")
    merged_payload["items"] = base_items + additions
    merged_statement = FinancialStatement.model_validate(merged_payload)

    target_output_dir = output_dir or statement_json_path.parent
    export(merged_statement, target_output_dir, pdf_path)

    print(f"Added {len(additions)} KPI metrics: {', '.join(item['normalized_label'] for item in additions)}")
    return len(additions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract MAU/DAU/paid subscribers from a specific PDF page and merge into statement output."
    )
    parser.add_argument("--pdf", required=True, help="Path to source PDF file.")
    parser.add_argument(
        "--statement-json",
        required=True,
        help="Path to existing *_statement.json output to merge KPIs into.",
    )
    parser.add_argument(
        "--output-dir",
        required=False,
        help="Optional output directory (defaults to statement JSON folder).",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=61,
        help="1-based source PDF page containing MAU/DAU/paid subscribers (default: 61).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_kpi_fallback(
        pdf_path=Path(args.pdf),
        statement_json_path=Path(args.statement_json),
        output_dir=Path(args.output_dir) if args.output_dir else None,
        source_page=args.page,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())