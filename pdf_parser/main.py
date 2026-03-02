import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv

from models.schemas import FinancialStatement
from processors.azure_engine import get_raw_azure_data
from processors.docling_engine import extract_financial_tables
from processors.mapper import map_table_cells_to_statement


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

    return get_raw_azure_data(pdf_path)


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
    if engine == "docling":
        normalized_cells = []
        next_row_offset = 0
        for table_markdown in extracted_data:
            table_cells = _parse_markdown_table(table_markdown)
            for cell in table_cells:
                normalized_cells.append(
                    {
                        "row": cell["row"] + next_row_offset,
                        "column": cell["column"],
                        "text": cell["text"],
                    }
                )

            if table_cells:
                next_row_offset = max(c["row"] for c in normalized_cells) + 1

        return normalized_cells

    normalized_cells = []
    for table in extracted_data.tables:
        for cell in table.cells:
            normalized_cells.append(
                {
                    "row": cell.row_index,
                    "column": cell.column_index,
                    "text": cell.content or "",
                }
            )
    return normalized_cells


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
        "",
        "## Line Items",
        "",
        "| Label | Normalized | Value | Unit | Scale | YoY | Columns |",
        "|---|---|---:|---|---|---:|---|",
    ]

    for item in statement.items:
        columns_preview = ", ".join(
            "" if value is None else str(value)
            for value in (item.column_values or [])
        )
        markdown_lines.append(
            f"| {item.label} | {item.normalized_label or ''} | {item.value if item.value is not None else ''} | {item.unit} | {item.scale} | {item.yoy_change if item.yoy_change is not None else ''} | {columns_preview} |"
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