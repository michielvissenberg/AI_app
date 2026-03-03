import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv

from models.schemas import FinancialStatement
from processors.azure_engine import extract_financial_tables as extract_financial_tables_azure
from processors.docling_engine import extract_financial_tables
from processors.mapper import map_table_cells_to_statement


def _escape_markdown_cell(value):
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("\n", " ").replace("\r", " ")
    return text


def extract(
    pdf_path: str,
    engine: str,
    docling_device: str = "auto",
    docling_chunk_size: int = 8,
    docling_num_threads: int = 4,
):
    if engine == "docling":
        return extract_financial_tables(
            pdf_path,
            device=docling_device,
            chunk_size=docling_chunk_size,
            num_threads=docling_num_threads,
        )

    if not os.getenv("AZURE_ENDPOINT") or not os.getenv("AZURE_KEY"):
        raise ValueError("Azure engine requires AZURE_ENDPOINT and AZURE_KEY in environment.")

    return extract_financial_tables_azure(pdf_path)


def _parse_markdown_table(markdown_table: str):
    rows = []
    for line in markdown_table.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue

        if all(part.replace(":", "").replace("-", "") == "" for part in cells):
            continue

        rows.append(cells)

    if not rows:
        return []

    if len(rows) > 1:
        rows = rows[1:]

    normalized_cells = []
    for row_index, row in enumerate(rows):
        for column_index, text in enumerate(row):
            normalized_cells.append({"row": row_index, "column": column_index, "text": text})

    return normalized_cells


def normalize(extracted_data, engine: str):
    if not isinstance(extracted_data, list):
        raise TypeError("Expected normalized list of table cells from extraction engine.")

    for cell in extracted_data:
        if not isinstance(cell, dict) or not {"row", "column", "text"}.issubset(cell.keys()):
            raise TypeError("Normalized cell must contain row, column, and text keys.")

    return extracted_data


def map_statement(company_name: str, ticker: str, report_type: str, period_ending: str, table_cells):
    return map_table_cells_to_statement(
        company_name=company_name,
        report_type=report_type,
        date=period_ending,
        table_cells=table_cells,
        ticker=ticker,
    )


def validate(statement: FinancialStatement) -> FinancialStatement:
    return FinancialStatement.model_validate(statement.model_dump())


def export(statement: FinancialStatement, output_dir: Path, source_pdf: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = source_pdf.stem

    json_path = output_dir / f"{base_name}_statement.json"
    markdown_path = output_dir / f"{base_name}_statement.md"

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(statement.model_dump(mode="json"), handle, indent=2)

    markdown_lines = [
        "# Financial Statement",
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
        "## Line Items",
        "",
        "| Label | Canonical Label | Statement Type | Value | Unit | Scale | Parse Status | YoY | YoY Unit | Current Period Value | Prior Period Value | Current Period Label | Prior Period Label | Current Period Column | Prior Period Column | Column Values JSON | Column Units JSON | Column Scales JSON | Column Parse Statuses JSON | Supplemental Metrics JSON |",
        "|---|---|---|---:|---|---|---|---:|---|---:|---:|---|---|---:|---:|---|---|---|---|---|",
    ]

    for item in statement.items:
        column_values_json = json.dumps(item.column_values or [])
        column_units_json = json.dumps(item.column_units or [])
        column_scales_json = json.dumps(item.column_scales or [])
        column_parse_statuses_json = json.dumps(item.column_parse_statuses or [])
        supplemental_metrics_json = json.dumps(item.supplemental_metrics or {})

        markdown_lines.append(
            "| "
            f"{item.label} | "
            f"{item.normalized_label or ''} | "
            f"{item.statement_type or ''} | "
            f"{item.value if item.value is not None else ''} | "
            f"{item.unit} | "
            f"{item.scale} | "
            f"{item.parse_status or ''} | "
            f"{item.yoy_change if item.yoy_change is not None else ''} | "
            f"{item.yoy_unit or ''} | "
            f"{item.current_period_value if item.current_period_value is not None else ''} | "
            f"{item.prior_period_value if item.prior_period_value is not None else ''} | "
            f"{item.current_period_label or ''} | "
            f"{item.prior_period_label or ''} | "
            f"{item.current_period_column if item.current_period_column is not None else ''} | "
            f"{item.prior_period_column if item.prior_period_column is not None else ''} | "
            f"{_escape_markdown_cell(column_values_json)} | "
            f"{_escape_markdown_cell(column_units_json)} | "
            f"{_escape_markdown_cell(column_scales_json)} | "
            f"{_escape_markdown_cell(column_parse_statuses_json)} | "
            f"{_escape_markdown_cell(supplemental_metrics_json)} |"
        )

    with open(markdown_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(markdown_lines) + "\n")

    return json_path, markdown_path


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
    return export(validated_statement, output_dir, pdf_path)


def main():
    load_dotenv()

    project_root = Path(__file__).resolve().parents[1]

    parser = argparse.ArgumentParser(description="Run financial PDF parsing pipeline.")
    parser.add_argument("--pdf", default=str(project_root / "data" / "testdocument.pdf"))
    parser.add_argument("--engine", choices=["docling", "azure"], default="docling")
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
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    json_path, markdown_path = run_pipeline(
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


if __name__ == "__main__":
    main()