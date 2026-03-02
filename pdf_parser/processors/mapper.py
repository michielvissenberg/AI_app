import re

from models.schemas import FinancialLineItem, FinancialStatement
from processors.cleaners import is_percentage_value, normalize_label, parse_financial_value


def _looks_like_data_value(value_text: str) -> bool:
    normalized = (value_text or "").strip().lower()
    if not normalized:
        return False

    if normalized in {"value", "amount", "current", "prior", "current year", "prior year"}:
        return False

    if normalized in {"-", "—", "–"}:
        return True

    return any(ch.isdigit() for ch in normalized) or (
        normalized.startswith("(") and normalized.endswith(")")
    )


def _is_header_like_row(label_text: str, value_text: str) -> bool:
    label = (label_text or "").strip().lower()
    value = (value_text or "").strip().lower()

    if not label:
        return True

    if re.match(r"^item\s+\d+[a-z]?\.?$", label):
        return True

    header_phrases = [
        "consolidated statements",
        "for the years ended",
        "as of september",
        "notes to consolidated financial statements",
        "reports of independent registered public accounting firm",
        "table of contents",
    ]
    if any(phrase in label for phrase in header_phrases):
        return True

    if re.fullmatch(r"\d{1,3}", value) and len(label.split()) >= 4:
        return True

    return False


def _is_reference_only_label(label_text: str) -> bool:
    label = (label_text or "").strip()
    if not label:
        return True

    exhibit_code_pattern = r"^\d{1,3}(?:\.\d{1,3})+(?:\*+)?(?:\s+\d{1,3}(?:\.\d{1,3})+\*+)*$"
    numeric_star_pattern = r"^\d{2,3}\*+$"

    return bool(re.match(exhibit_code_pattern, label) or re.match(numeric_star_pattern, label))


def _extract_value_columns(row: dict):
    extracted_columns = []
    for column_index in sorted(row.keys()):
        if column_index == 0:
            continue

        raw_text = (row[column_index] or "").strip()
        if not raw_text:
            continue

        if not _looks_like_data_value(raw_text) and not is_percentage_value(raw_text):
            continue

        parsed = parse_financial_value(raw_text)

        extracted_columns.append(
            {
                "column": column_index,
                "raw_text": raw_text,
                "value": parsed["value"],
                "unit": parsed["unit"],
                "scale": parsed["scale"],
                "parse_status": parsed["parse_status"],
            }
        )

    return extracted_columns


def _is_contextual_percentage_row(label_text: str) -> bool:
    normalized = normalize_label(label_text)
    return normalized in {
        "percentage_of_total_net_sales",
        "percent_of_net_sales",
        "%_of_net_sales",
    }

def map_table_cells_to_statement(company_name, report_type, date, table_cells, ticker="TBD"):
    """
    Iterates through Azure analysis results to populate a validated FinancialStatement.

    This function filters through the 'azure_result' tables, cleans each row's 
    values using the cleaner utilities, and initializes Pydantic models (FinancialLineItem).
    It ensures that the final object adheres to the project's 'Golden Standard' schema.

    Args:
        company_name (str): Name of the entity (e.g., 'Apple Inc.').
        report_type (str): Type of filing (e.g., '10-K' or '10-Q').
        date (str): The period ending date for the statement.
        azure_result (AnalyzeResult): The raw object returned by get_raw_azure_data.

    Returns:
        models.schemas.FinancialStatement: A fully validated Pydantic object 
            ready for database insertion.
    """
    line_items = []
    
    rows = {}
    for cell in table_cells:
        row_index = cell.get("row")
        column_index = cell.get("column")
        text = cell.get("text", "")

        if row_index is None or column_index is None:
            continue

        if row_index not in rows:
            rows[row_index] = {}
        rows[row_index][column_index] = text

    for row_idx in sorted(rows.keys()):
        row = rows[row_idx]
        if 0 not in row:
            continue

        label_text = (row[0] or "").strip()
        if _is_reference_only_label(label_text):
            continue

        value_columns = _extract_value_columns(row)

        if not label_text or not value_columns:
            continue

        first_column_text = value_columns[0]["raw_text"]

        if _is_header_like_row(label_text, first_column_text):
            continue

        if _is_contextual_percentage_row(label_text) and line_items:
            previous_item = line_items[-1]
            if previous_item.supplemental_metrics is None:
                previous_item.supplemental_metrics = {}

            previous_item.supplemental_metrics[normalize_label(label_text)] = [
                col["value"] for col in value_columns
            ]

            if previous_item.yoy_change is None:
                second_or_first = value_columns[1] if len(value_columns) > 1 else value_columns[0]
                if second_or_first["unit"] == "%":
                    previous_item.yoy_change = second_or_first["value"]
                    previous_item.yoy_unit = "%"
            continue

        primary_column = value_columns[0]
        column_values = [col["value"] for col in value_columns]
        column_units = [col["unit"] for col in value_columns]
        column_scales = [col["scale"] for col in value_columns]
        column_parse_statuses = [col["parse_status"] for col in value_columns]

        yoy_change = None
        yoy_unit = None
        if len(value_columns) > 1 and value_columns[1]["unit"] == "%":
            yoy_change = value_columns[1]["value"]
            yoy_unit = "%"

        item = FinancialLineItem(
            label=label_text,
            normalized_label=normalize_label(label_text),
            value=primary_column["value"],
            unit=primary_column["unit"],
            scale=primary_column["scale"],
            column_values=column_values,
            column_units=column_units,
            column_scales=column_scales,
            column_parse_statuses=column_parse_statuses,
            parse_status=primary_column["parse_status"],
            yoy_change=yoy_change,
            yoy_unit=yoy_unit,
        )
        line_items.append(item)

    return FinancialStatement(
        company_name=company_name,
        ticker=ticker,
        report_type=report_type,
        period_ending=date,
        items=line_items
    )


def map_azure_table_to_statement(company_name, report_type, date, azure_table_cells):
    return map_table_cells_to_statement(
        company_name=company_name,
        report_type=report_type,
        date=date,
        table_cells=azure_table_cells,
    )