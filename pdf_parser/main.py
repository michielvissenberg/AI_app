import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

from models.schemas import FinancialStatement
from processors.docling_engine import extract_financial_tables
from processors.error_handling import ErrorCode, PipelineError, configure_logger, log_event
from processors.mapper import map_table_cells_to_statement
"""
example use: 
python .\pdf_parser\main.py --pdf .\data_raw\DUOL.pdf --engine docling --docling-device cuda --company "Duolingo" --ticker DUOL --report-type 10-K --period-ending 2025-12-31 --output-dir .\data_raw\ 
"""

LOGGER = configure_logger(__name__)


def _escape_markdown_cell(value):
    """Escapes markdown-sensitive characters for stable LLM-readable output."""
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("\n", " ").replace("\r", " ")
    return text


def _format_number(value):
    """Formats numeric values into compact strings while preserving null semantics."""
    if value is None:
        return "null"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value)}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def extract(
    pdf_path: str,
    engine: str,
    docling_device: str = "auto",
    docling_chunk_size: int = 8,
    docling_num_threads: int = 4,
):
    """Dispatches extraction to the selected engine and validates engine configuration."""
    log_event(
        LOGGER,
        logging.INFO,
        "pipeline_extract_started",
        engine=engine,
        pdf_path=pdf_path,
        docling_device=docling_device,
        docling_chunk_size=docling_chunk_size,
        docling_num_threads=docling_num_threads,
    )

    if engine == "docling":
        try:
            extracted = extract_financial_tables(
                pdf_path,
                device=docling_device,
                chunk_size=docling_chunk_size,
                num_threads=docling_num_threads,
            )
            log_event(LOGGER, logging.INFO, "pipeline_extract_completed", engine=engine, cells=len(extracted))
            return extracted
        except PipelineError:
            raise
        except Exception as exc:
            raise PipelineError(
                ErrorCode.EXTRACTION_ERROR,
                "Docling extraction failed in pipeline extract stage.",
                recoverable=True,
                context={"engine": engine, "pdf_path": pdf_path},
                cause=exc,
            ) from exc

    raise PipelineError(
        ErrorCode.CONFIGURATION_ERROR,
        "Only docling engine is supported in this pipeline.",
        recoverable=False,
        context={"engine": engine},
    )


def normalize(extracted_data, engine: str):
    """Validates normalized extraction shape before mapping stage execution."""
    if not isinstance(extracted_data, list):
        raise PipelineError(
            ErrorCode.NORMALIZATION_ERROR,
            "Expected normalized list of table cells from extraction engine.",
            recoverable=False,
            context={"engine": engine, "received_type": type(extracted_data).__name__},
        )

    for cell in extracted_data:
        if not isinstance(cell, dict) or not {"row", "column", "text"}.issubset(cell.keys()):
            raise PipelineError(
                ErrorCode.NORMALIZATION_ERROR,
                "Normalized cell must contain row, column, and text keys.",
                recoverable=False,
                context={"engine": engine, "invalid_cell": str(cell)},
            )

    log_event(LOGGER, logging.INFO, "pipeline_normalize_completed", engine=engine, cells=len(extracted_data))
    return extracted_data


def map_statement(company_name: str, ticker: str, report_type: str, period_ending: str, table_cells):
    """Maps normalized table cells into the FinancialStatement domain model."""
    try:
        statement = map_table_cells_to_statement(
            company_name=company_name,
            report_type=report_type,
            date=period_ending,
            table_cells=table_cells,
            ticker=ticker,
        )
        log_event(LOGGER, logging.INFO, "pipeline_map_completed", items=len(statement.items))
        return statement
    except Exception as exc:
        raise PipelineError(
            ErrorCode.MAPPING_ERROR,
            "Failed to map normalized cells to financial statement.",
            recoverable=False,
            context={"company_name": company_name, "ticker": ticker, "report_type": report_type},
            cause=exc,
        ) from exc


def validate(statement: FinancialStatement) -> FinancialStatement:
    """Runs schema validation to enforce canonical financial statement shape."""
    try:
        validated = FinancialStatement.model_validate(statement.model_dump())
        log_event(LOGGER, logging.INFO, "pipeline_validate_completed", items=len(validated.items))
        return validated
    except Exception as exc:
        raise PipelineError(
            ErrorCode.VALIDATION_ERROR,
            "Financial statement schema validation failed.",
            recoverable=False,
            context={"company_name": statement.company_name, "ticker": statement.ticker},
            cause=exc,
        ) from exc


_STATEMENT_EXPORT_ORDER = {
    "income_statement": 0,
    "balance_sheet": 1,
    "cash_flow_statement": 2,
    "equity_statement": 3,
    "unclassified": 4,
}


_PREFERRED_STATEMENT_TYPE_BY_LABEL = {
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


_CRITICAL_KPI_ANCHORS = {"revenue", "net_income", "total_assets"}


def _label_confidence_score(item) -> int:
    """Scores the confidence level of a normalized label match."""
    normalized_label = (item.normalized_label or "").strip().lower()
    raw_label = (item.label or "").strip().lower()

    if not normalized_label:
        return 0
    if normalized_label == raw_label:
        return 1
    return 2


def _dedup_group_key(item):
    """Builds a grouping key for identifying duplicate statement items."""
    normalized_label = (item.normalized_label or "").strip().lower()
    fallback_label = (item.label or "").strip().lower()
    statement_type = item.statement_type or "unclassified"
    current_period_label = (item.current_period_label or "").strip().lower()
    prior_period_label = (item.prior_period_label or "").strip().lower()
    current_period_column = item.current_period_column if item.current_period_column is not None else -1
    prior_period_column = item.prior_period_column if item.prior_period_column is not None else -1

    return (
        normalized_label if normalized_label else fallback_label,
        statement_type,
        current_period_label,
        prior_period_label,
        current_period_column,
        prior_period_column,
    )


def _dedup_candidate_score(item):
    """Ranks an item candidate within a duplicate group for selection as the winner."""
    preferred_statement_type = _PREFERRED_STATEMENT_TYPE_BY_LABEL.get((item.normalized_label or "").strip().lower())
    statement_type = item.statement_type or ""
    parse_status = (item.parse_status or "").strip().lower()

    points = 0
    if parse_status == "ok":
        points += 4
    elif parse_status in {"ambiguous", "parse_error"}:
        points -= 2

    has_current = item.current_period_value is not None
    has_prior = item.prior_period_value is not None
    if has_current:
        points += 5
    if has_prior:
        points += 3

    points += _label_confidence_score(item) * 2

    preferred_rank = 1
    if preferred_statement_type:
        if statement_type == preferred_statement_type:
            points += 4
            preferred_rank = 1
        else:
            points -= 4
            preferred_rank = 0

    fallback_value = item.current_period_value if item.current_period_value is not None else item.value
    magnitude = abs(float(fallback_value)) if fallback_value not in (None, "") else 0.0

    return (
        preferred_rank,
        points,
        int(has_current),
        int(has_prior),
        magnitude,
    )


def _summarize_candidate(index, item):
    """Extracts and summarizes key fields from a candidate item for diagnostic reporting."""
    return {
        "source_index": index,
        "label": item.label,
        "normalized_label": item.normalized_label,
        "statement_type": item.statement_type,
        "statement_type_confidence": item.statement_type_confidence,
        "period_alignment_confidence": item.period_alignment_confidence,
        "period_alignment_warning": item.period_alignment_warning,
        "parse_status": item.parse_status,
        "current_period_value": item.current_period_value,
        "prior_period_value": item.prior_period_value,
    }


def _is_high_confidence_anchor_candidate(item) -> bool:
    """Returns True when an item can participate in anchor winner selection."""
    return (
        (item.statement_type_confidence or "") == "high"
        and (item.period_alignment_confidence or "") == "high"
        and (item.parse_status or "") != "ambiguous"
    )


def _deduplicate_statement_items(statement: FinancialStatement):
    """Deduplicates statement items and returns diagnostics for collision groups."""
    grouped = defaultdict(list)
    for idx, item in enumerate(statement.items):
        grouped[_dedup_group_key(item)].append((idx, item))

    deduped_items = []
    duplicate_collisions = []

    for group_key, group_entries in grouped.items():
        label_key = (group_key[0] or "").strip().lower()
        eligible_entries = group_entries
        if label_key in _CRITICAL_KPI_ANCHORS:
            high_confidence_entries = [
                entry for entry in group_entries if _is_high_confidence_anchor_candidate(entry[1])
            ]
            if high_confidence_entries:
                eligible_entries = high_confidence_entries

        if len(eligible_entries) == 1:
            deduped_items.append(eligible_entries[0][1])
            continue

        winner_index, winner_item = max(eligible_entries, key=lambda entry: _dedup_candidate_score(entry[1]))
        deduped_items.append(winner_item)

        rejected = [
            _summarize_candidate(index=idx, item=item)
            for idx, item in group_entries
            if idx != winner_index
        ]

        duplicate_collisions.append(
            {
                "group_key": {
                    "label": group_key[0],
                    "statement_type": group_key[1],
                    "current_period_label": group_key[2],
                    "prior_period_label": group_key[3],
                    "current_period_column": group_key[4],
                    "prior_period_column": group_key[5],
                },
                "collision_count": len(group_entries),
                "winner": _summarize_candidate(index=winner_index, item=winner_item),
                "rejected_candidates": rejected,
            }
        )

    deduped_statement = statement.model_copy(update={"items": deduped_items})
    diagnostics = {
        "total_items_before": len(statement.items),
        "total_items_after": len(deduped_items),
        "duplicates_removed": len(statement.items) - len(deduped_items),
        "collision_groups": len(duplicate_collisions),
        "collisions": duplicate_collisions,
    }

    return deduped_statement, diagnostics


def _item_export_sort_key(item):
    """Builds a deterministic sort key for stable JSON/markdown exports."""
    statement_type = item.statement_type if item.statement_type in _STATEMENT_EXPORT_ORDER else "unclassified"
    normalized_label = (item.normalized_label or "").strip().lower()
    raw_label = (item.label or "").strip().lower()
    current_period_label = (item.current_period_label or "").strip().lower()
    prior_period_label = (item.prior_period_label or "").strip().lower()
    current_period_column = item.current_period_column if item.current_period_column is not None else 10**6
    prior_period_column = item.prior_period_column if item.prior_period_column is not None else 10**6
    parse_status = (item.parse_status or "").strip().lower()

    return (
        _STATEMENT_EXPORT_ORDER[statement_type],
        normalized_label,
        raw_label,
        current_period_label,
        prior_period_label,
        current_period_column,
        prior_period_column,
        parse_status,
    )


def _sorted_statement_for_export(statement: FinancialStatement) -> FinancialStatement:
    """Returns a copy of statement with a deterministic item order for export."""
    sorted_items = sorted(statement.items, key=_item_export_sort_key)
    return statement.model_copy(update={"items": sorted_items})


def export(statement: FinancialStatement, output_dir: Path, source_pdf: Path, duplicate_diagnostics=None):
    """Exports canonical JSON and compact markdown narrative outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = source_pdf.stem
    export_statement = _sorted_statement_for_export(statement)

    json_path = output_dir / f"{base_name}_statement.json"
    markdown_path = output_dir / f"{base_name}_statement.md"
    diagnostics_path = output_dir / f"{base_name}_duplicate_diagnostics.json"

    try:
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(export_statement.model_dump(mode="json"), handle, indent=2)
    except Exception as exc:
        raise PipelineError(
            ErrorCode.EXPORT_ERROR,
            "Failed to write canonical JSON output.",
            recoverable=False,
            context={"json_path": str(json_path)},
            cause=exc,
        ) from exc

    statement_sections = {
        "income_statement": "Income Statement",
        "balance_sheet": "Balance Sheet",
        "cash_flow_statement": "Cash Flow Statement",
        "equity_statement": "Equity Statement",
        "unclassified": "Unclassified",
    }

    grouped_items = {key: [] for key in statement_sections.keys()}
    for item in export_statement.items:
        section_key = item.statement_type if item.statement_type in statement_sections else "unclassified"
        grouped_items[section_key].append(item)

    markdown_lines = [
        "# Financial Statement Narrative",
        "",
        f"- Company: {statement.company_name}",
        f"- Ticker: {statement.ticker}",
        f"- Report Type: {statement.report_type}",
        f"- Period Ending: {statement.period_ending}",
        f"- Extracted At: {statement.extracted_at.isoformat()}",
        f"- Source PDF: {source_pdf.name}",
        "",
        "## Extraction Metadata",
        "",
        "- Mapping Strategy: rule_based_statement_and_period_classification",
        "- Statement Scope: core_10k_income_balance_sheet_cash_flow_equity",
        "- Period Roles: inferred_current_and_prior_from_headers_and_year_tokens",
        "",
        "## Narrative Format",
        "",
        "Each metric line uses: canonical_label | raw_label | unit | scale | current | prior | yoy | parse_status | statement_confidence | period_confidence",
    ]

    for section_key, section_title in statement_sections.items():
        items = grouped_items.get(section_key, [])
        if not items:
            continue

        markdown_lines.extend([
            "",
            f"## {section_title}",
            "",
        ])

        for item in items:
            canonical_label = _escape_markdown_cell(item.normalized_label or "")
            raw_label = _escape_markdown_cell(item.label)
            unit = _escape_markdown_cell(item.unit)
            scale = _escape_markdown_cell(item.scale)
            current_value = _format_number(item.current_period_value)
            prior_value = _format_number(item.prior_period_value)
            yoy_value = _format_number(item.yoy_change)
            yoy_unit = _escape_markdown_cell(item.yoy_unit or "")
            parse_status = _escape_markdown_cell(item.parse_status or "")
            statement_confidence = _escape_markdown_cell(item.statement_type_confidence or "")
            period_confidence = _escape_markdown_cell(item.period_alignment_confidence or "")
            period_warning = _escape_markdown_cell(item.period_alignment_warning or "")

            period_meta = []
            if item.current_period_label:
                period_meta.append(f"current_label={_escape_markdown_cell(item.current_period_label)}")
            if item.prior_period_label:
                period_meta.append(f"prior_label={_escape_markdown_cell(item.prior_period_label)}")
            if item.current_period_column is not None:
                period_meta.append(f"current_col={item.current_period_column}")
            if item.prior_period_column is not None:
                period_meta.append(f"prior_col={item.prior_period_column}")

            period_meta_text = f"; {'; '.join(period_meta)}" if period_meta else ""

            markdown_lines.append(
                "- "
                f"{canonical_label} | raw={raw_label} | unit={unit} | scale={scale} "
                f"| current={current_value} | prior={prior_value} "
                f"| yoy={yoy_value}{yoy_unit if yoy_unit else ''} | parse_status={parse_status} "
                f"| statement_confidence={statement_confidence} | period_confidence={period_confidence}"
                f"{period_meta_text}"
            )

            if period_warning:
                markdown_lines.append(f"  warning: {period_warning}")

    try:
        with open(markdown_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(markdown_lines) + "\n")
    except Exception as exc:
        raise PipelineError(
            ErrorCode.EXPORT_ERROR,
            "Failed to write markdown narrative output.",
            recoverable=False,
            context={"markdown_path": str(markdown_path)},
            cause=exc,
        ) from exc

    if duplicate_diagnostics is not None:
        try:
            with open(diagnostics_path, "w", encoding="utf-8") as handle:
                json.dump(duplicate_diagnostics, handle, indent=2)
        except Exception as exc:
            raise PipelineError(
                ErrorCode.EXPORT_ERROR,
                "Failed to write duplicate diagnostics output.",
                recoverable=False,
                context={"diagnostics_path": str(diagnostics_path)},
                cause=exc,
            ) from exc

    log_event(
        LOGGER,
        logging.INFO,
        "pipeline_export_completed",
        json_path=str(json_path),
        markdown_path=str(markdown_path),
        diagnostics_path=str(diagnostics_path),
        items=len(export_statement.items),
    )

    return json_path, markdown_path, diagnostics_path


def run_pipeline(
    pdf_path: Path,
    engine: str,
    company_name: str,
    ticker: str,
    report_type: str,
    period_ending: str,
    output_dir: Path,
    docling_device: str = "auto",
    docling_chunk_size: int = 8,
    docling_num_threads: int = 4,
):
    """Executes extract-normalize-map-validate-export with structured stage logging."""
    log_event(
        LOGGER,
        logging.INFO,
        "pipeline_started",
        pdf_path=str(pdf_path),
        engine=engine,
        company_name=company_name,
        ticker=ticker,
        report_type=report_type,
        period_ending=period_ending,
    )
    extracted = extract(
        str(pdf_path),
        engine,
        docling_device=docling_device,
        docling_chunk_size=docling_chunk_size,
        docling_num_threads=docling_num_threads,
    )
    normalized_cells = normalize(extracted, engine)
    mapped_statement = map_statement(company_name, ticker, report_type, period_ending, normalized_cells)
    validated_statement = validate(mapped_statement)
    deduped_statement, dedup_diagnostics = _deduplicate_statement_items(validated_statement)
    outputs = export(deduped_statement, output_dir, pdf_path, duplicate_diagnostics=dedup_diagnostics)
    log_event(
        LOGGER,
        logging.INFO,
        "pipeline_completed",
        json_path=str(outputs[0]),
        markdown_path=str(outputs[1]),
        diagnostics_path=str(outputs[2]),
    )
    return outputs


def main():
    """CLI entrypoint for running the financial parsing and export pipeline."""
    load_dotenv()

    project_root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(description="Run financial PDF parsing pipeline.")
    parser.add_argument("--pdf", default=str(project_root / "data" / "testdocument.pdf"))
    parser.add_argument("--engine", choices=["docling"], default="docling")
    parser.add_argument("--company", default="Unknown Company")
    parser.add_argument("--ticker", default="TBD")
    parser.add_argument("--report-type", default="10-K")
    parser.add_argument("--period-ending", default="1970-01-01")
    parser.add_argument("--output-dir", default=str(project_root / "data"))
    parser.add_argument("--docling-device", choices=["auto", "cpu", "cuda", "mps", "xpu"], default="auto")
    parser.add_argument("--docling-chunk-size", type=int, default=8)
    parser.add_argument("--docling-num-threads", type=int, default=4)
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise PipelineError(
            ErrorCode.INVALID_INPUT,
            "PDF file path does not exist.",
            recoverable=False,
            context={"pdf_path": str(pdf_path)},
        )

    try:
        json_path, markdown_path, diagnostics_path = run_pipeline(
            pdf_path=pdf_path,
            engine=args.engine,
            company_name=args.company,
            ticker=args.ticker,
            report_type=args.report_type,
            period_ending=args.period_ending,
            output_dir=Path(args.output_dir),
            docling_device=args.docling_device,
            docling_chunk_size=max(1, args.docling_chunk_size),
            docling_num_threads=max(1, args.docling_num_threads),
        )

        print("Pipeline completed successfully.")
        print(f"JSON export: {json_path}")
        print(f"Markdown export: {markdown_path}")
        print(f"Duplicate diagnostics export: {diagnostics_path}")
    except PipelineError as exc:
        log_event(LOGGER, logging.ERROR, "pipeline_failed", **exc.to_dict())
        print(f"Pipeline failed [{exc.code.value}]: {exc.message}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()