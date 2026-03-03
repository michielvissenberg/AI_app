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


def _format_number(value):
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

    statement_sections = {
        "income_statement": "Income Statement",
        "balance_sheet": "Balance Sheet",
        "cash_flow_statement": "Cash Flow Statement",
        "equity_statement": "Equity Statement",
        "unclassified": "Unclassified",
    }

    grouped_items = {key: [] for key in statement_sections.keys()}
    for item in statement.items:
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
        "Each metric line uses: canonical_label | raw_label | unit | scale | current | prior | yoy | parse_status",
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
                f"| yoy={yoy_value}{yoy_unit if yoy_unit else ''} | parse_status={parse_status}{period_meta_text}"
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