import re
import logging
from typing import Dict, List, Optional

from models.schemas import FinancialLineItem, FinancialStatement
from processors.cleaners import is_percentage_value, normalize_label, parse_financial_value
from processors.error_handling import configure_logger, log_event


LOGGER = configure_logger(__name__)


STATEMENT_TYPE_RULES = {
    "income_statement": [
        "statements of operations",
        "statement of operations",
        "statements of income",
        "statement of income",
        "income statements",
    ],
    "balance_sheet": [
        "balance sheets",
        "statement of financial position",
        "financial position",
        "assets and liabilities",
    ],
    "cash_flow_statement": [
        "statements of cash flows",
        "statement of cash flows",
        "cash flows",
    ],
    "equity_statement": [
        "statements of shareholders' equity",
        "statement of shareholders' equity",
        "statements of stockholders' equity",
        "statement of stockholders' equity",
        "statement of changes in equity",
    ],
}


CANONICAL_LINE_ITEM_RULES = {
    "global": [
        (r"^total\s+net\s+sales$", "revenue"),
        (r"^net\s+sales$", "revenue"),
        (r"^revenue$", "revenue"),
        (r"^net\s+income$", "net_income"),
        (r"^total\s+assets$", "total_assets"),
        (r"^total\s+liabilities$", "total_liabilities"),
    ],
    "income_statement": [
        (r"^products$", "product_revenue"),
        (r"^services(\s*\(\d+\))?$", "service_revenue"),
        (r"^total\s+cost\s+of\s+sales$", "cost_of_revenue"),
        (r"^gross\s+margin$", "gross_profit"),
        (r"^total\s+gross\s+margin$", "gross_profit"),
        (r"^operating\s+income$", "operating_income"),
        (r"^provision\s+for\s+income\s+taxes$", "income_tax_expense"),
        (r"^basic\s+earnings\s+per\s+share$", "basic_eps"),
        (r"^diluted\s+earnings\s+per\s+share$", "diluted_eps"),
    ],
    "balance_sheet": [
        (r"^cash\s+and\s+cash\s+equivalents$", "cash_and_cash_equivalents"),
        (r"^marketable\s+securities$", "marketable_securities"),
        (r"^accounts\s+receivable,\s*net$", "accounts_receivable_net"),
        (r"^inventories$", "inventories"),
        (r"^total\s+current\s+assets$", "total_current_assets"),
        (r"^total\s+current\s+liabilities$", "total_current_liabilities"),
        (r"^total\s+shareholders'?\s+equity$", "total_shareholders_equity"),
        (r"^total\s+liabilities\s+and\s+shareholders'?\s+equity$", "total_liabilities_and_equity"),
    ],
    "cash_flow_statement": [
        (r"^cash\s+generated\s+by\s+operating\s+activities$", "net_cash_from_operating_activities"),
        (r"^cash\s+generated\s+by\s+investing\s+activities$", "net_cash_from_investing_activities"),
        (r"^cash\s+used\s+in\s+financing\s+activities$", "net_cash_from_financing_activities"),
        (
            r"^cash,\s+cash\s+equivalents,\s+and\s+restricted\s+cash\s+and\s+cash\s+equivalents,\s+ending\s+balances$",
            "ending_cash_and_cash_equivalents",
        ),
    ],
    "equity_statement": [
        (r"^total\s+shareholders'?\s+equity,\s+beginning\s+balances$", "beginning_equity"),
        (r"^total\s+shareholders'?\s+equity,\s+ending\s+balances$", "ending_equity"),
        (r"^dividends\s+and\s+dividend\s+equivalents\s+declared$", "dividends_declared"),
    ],
}


CURRENT_PERIOD_HINTS = {"current", "latest", "most recent", "this year", "current year"}
PRIOR_PERIOD_HINTS = {"prior", "previous", "preceding", "last year", "prior year"}


def _looks_like_data_value(value_text: str) -> bool:
    """Heuristically determines whether a cell value looks like numeric table data."""
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
    """Identifies non-data header rows that should be skipped during mapping."""
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
    """Returns True when a label appears to be exhibit/reference metadata rather than a metric."""
    label = (label_text or "").strip()
    if not label:
        return True

    exhibit_code_pattern = r"^\d{1,3}(?:\.\d{1,3})+(?:\*+)?(?:\s+\d{1,3}(?:\.\d{1,3})+\*+)*$"
    numeric_star_pattern = r"^\d{2,3}\*+$"

    return bool(re.match(exhibit_code_pattern, label) or re.match(numeric_star_pattern, label))


def _extract_value_columns(row: dict):
    """Extracts parseable value columns from a normalized row map."""
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
    """Detects contextual percentage lines that augment the previous metric."""
    normalized = normalize_label(label_text)
    return normalized in {
        "percentage_of_total_net_sales",
        "percent_of_net_sales",
        "%_of_net_sales",
    }


def _normalize_for_rule(text: str) -> str:
    """Normalizes free text for rule matching by lowering case and collapsing whitespace."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _classify_statement_type(label_text: str) -> Optional[str]:
    """Classifies statement section headers into canonical 10-K statement types."""
    normalized = _normalize_for_rule(label_text)
    if not normalized:
        return None

    for statement_type, phrases in STATEMENT_TYPE_RULES.items():
        if any(phrase in normalized for phrase in phrases):
            return statement_type

    return None


def _classify_canonical_label(label_text: str, statement_type: Optional[str]) -> str:
    """Maps a raw row label to a canonical metric label using scoped regex rules."""
    normalized = _normalize_for_rule(label_text)
    scoped_rules = CANONICAL_LINE_ITEM_RULES.get(statement_type or "", [])

    for pattern, canonical_label in scoped_rules:
        if re.match(pattern, normalized):
            return canonical_label

    for pattern, canonical_label in CANONICAL_LINE_ITEM_RULES["global"]:
        if re.match(pattern, normalized):
            return canonical_label

    return normalize_label(label_text)


def _infer_statement_type_from_label_rules(label_text: str) -> Optional[str]:
    """Infers statement type from line-item label regex rules when header context drifts."""
    normalized = _normalize_for_rule(label_text)
    if not normalized:
        return None

    matched_types = []
    for statement_type, rules in CANONICAL_LINE_ITEM_RULES.items():
        if statement_type == "global":
            continue
        if any(re.match(pattern, normalized) for pattern, _ in rules):
            matched_types.append(statement_type)

    if len(matched_types) == 1:
        return matched_types[0]

    explicit_keyword_rules = [
        ("total net sales", "income_statement"),
        ("net sales", "income_statement"),
        ("revenue", "income_statement"),
        ("gross margin", "income_statement"),
        ("cash generated by", "cash_flow_statement"),
        ("cash used in", "cash_flow_statement"),
        ("cash and cash equivalents", "balance_sheet"),
        ("total assets", "balance_sheet"),
        ("total liabilities", "balance_sheet"),
        ("earnings per share", "income_statement"),
        ("net income", "income_statement"),
        ("operating income", "income_statement"),
    ]

    keyword_hits = {stype for phrase, stype in explicit_keyword_rules if phrase in normalized}
    if len(keyword_hits) == 1:
        return next(iter(keyword_hits))

    return None


def _extract_year_token(text: str) -> Optional[int]:
    """Extracts the latest year token from text when present."""
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text or "")
    if not years:
        return None
    return max(int(year) for year in years)


def _is_compact_period_header_text(text: str) -> bool:
    """Checks whether text is short/clean enough to be trusted as period header metadata."""
    normalized = _normalize_for_rule(text)
    if not normalized:
        return False

    if len(normalized) > 64:
        return False

    if normalized.count("|") > 0:
        return False

    if any(ch in normalized for ch in "{}[]"):
        return False

    return True


def _is_period_header_text(text: str) -> bool:
    """Determines whether text expresses period context such as year/current/prior hints."""
    normalized = _normalize_for_rule(text)
    if not normalized:
        return False

    if not _is_compact_period_header_text(normalized):
        return False

    if any(hint in normalized for hint in CURRENT_PERIOD_HINTS | PRIOR_PERIOD_HINTS):
        return True

    if _extract_year_token(normalized) is not None:
        return True

    period_phrases = {
        "for the year ended",
        "for the years ended",
        "as of",
        "fiscal year",
        "twelve months ended",
    }
    return any(phrase in normalized for phrase in period_phrases)


def _collect_period_column_context(rows: Dict[int, Dict[int, str]]) -> Dict[int, List[str]]:
    """Collects likely period header text per column from early table rows."""
    context: Dict[int, List[str]] = {}

    first_data_row = None
    for row_index in sorted(rows.keys()):
        row = rows[row_index]
        label_text = (row.get(0) or "").strip()
        if not label_text:
            continue

        candidate_values = [
            (row[column_index] or "").strip()
            for column_index in sorted(row.keys())
            if column_index != 0
        ]
        has_data_value = any(
            _looks_like_data_value(value_text) or is_percentage_value(value_text)
            for value_text in candidate_values
        )
        if has_data_value:
            first_data_row = row_index
            break

    header_row_cutoff = (first_data_row + 1) if first_data_row is not None else 20
    header_row_cutoff = max(5, min(header_row_cutoff, 30))

    for row_index in sorted(rows.keys()):
        if row_index > header_row_cutoff:
            continue

        row = rows[row_index]
        label_text = (row.get(0) or "").strip()
        label_is_period_header = _is_period_header_text(label_text)

        for column_index in sorted(row.keys()):
            if column_index == 0:
                continue

            text = (row[column_index] or "").strip()
            if not text:
                continue

            if not _is_compact_period_header_text(text):
                continue

            if label_is_period_header or _is_period_header_text(text):
                bucket = context.setdefault(column_index, [])
                if text not in bucket:
                    bucket.append(text)

                if len(bucket) > 3:
                    context[column_index] = bucket[:3]

    return context


def _infer_period_column_roles(rows: Dict[int, Dict[int, str]]) -> Dict[int, Dict[str, Optional[str]]]:
    """Infers current/prior roles for table columns from explicit hints and detected years."""
    context = _collect_period_column_context(rows)
    if not context:
        return {}

    role_map: Dict[int, Dict[str, Optional[str]]] = {}
    explicit_current = []
    explicit_prior = []
    year_candidates = []

    for column_index, header_texts in context.items():
        merged_text = " | ".join(header_texts)
        normalized = _normalize_for_rule(merged_text)
        detected_year = _extract_year_token(normalized)

        role = None
        if any(hint in normalized for hint in CURRENT_PERIOD_HINTS):
            explicit_current.append(column_index)
            role = "current"
        elif any(hint in normalized for hint in PRIOR_PERIOD_HINTS):
            explicit_prior.append(column_index)
            role = "prior"
        elif detected_year is not None:
            year_candidates.append((column_index, detected_year))

        role_map[column_index] = {
            "role": role,
            "label": merged_text or None,
            "year": str(detected_year) if detected_year is not None else None,
        }

    if explicit_current and explicit_prior:
        return role_map

    if year_candidates:
        ordered = sorted(year_candidates, key=lambda item: item[1], reverse=True)
        if ordered:
            role_map[ordered[0][0]]["role"] = "current"
        if len(ordered) > 1:
            role_map[ordered[1][0]]["role"] = "prior"

    return role_map


def _resolve_period_values(
    value_columns: List[Dict[str, object]],
    period_roles: Dict[int, Dict[str, Optional[str]]],
):
    """Resolves current/prior values and metadata from parsed row values and inferred column roles."""
    current_value = None
    prior_value = None
    current_label = None
    prior_label = None
    current_column = None
    prior_column = None

    monetary_columns = [col for col in value_columns if col.get("unit") != "%"]

    def _numeric_distance_from_current(candidate_value, current_value):
        if candidate_value is None or current_value is None:
            return float("inf")

        candidate_abs = abs(float(candidate_value)) + 1.0
        current_abs = abs(float(current_value)) + 1.0
        return abs(candidate_abs - current_abs) / current_abs

    for col in monetary_columns:
        column_index = col["column"]
        metadata = period_roles.get(column_index, {})
        role = metadata.get("role")

        if role == "current" and current_value is None:
            current_value = col["value"]
            current_label = metadata.get("label")
            current_column = column_index
        elif role == "prior" and prior_value is None:
            prior_value = col["value"]
            prior_label = metadata.get("label")
            prior_column = column_index

    if current_value is None and monetary_columns:
        first = monetary_columns[0]
        current_value = first["value"]
        current_column = first["column"]
        current_label = period_roles.get(first["column"], {}).get("label")

    if prior_value is None and len(monetary_columns) > 1:
        current_unit = None
        for col in monetary_columns:
            if col["column"] == current_column:
                current_unit = col.get("unit")
                break

        candidate_columns = [
            col
            for col in monetary_columns
            if col["column"] != current_column and (current_unit is None or col.get("unit") == current_unit)
        ]

        if candidate_columns:
            explicit_prior = None
            for col in candidate_columns:
                metadata = period_roles.get(col["column"], {})
                if metadata.get("role") == "prior":
                    explicit_prior = col
                    break

            if explicit_prior is not None:
                selected_prior = explicit_prior
            else:
                selected_prior = sorted(
                    candidate_columns,
                    key=lambda col: (
                        _numeric_distance_from_current(col.get("value"), current_value),
                        0 if current_column is not None and col["column"] > current_column else 1,
                        abs((col["column"] - current_column) if current_column is not None else col["column"]),
                    ),
                )[0]

            prior_value = selected_prior["value"]
            prior_column = selected_prior["column"]
            prior_label = period_roles.get(selected_prior["column"], {}).get("label")

    return {
        "current_period_value": current_value,
        "prior_period_value": prior_value,
        "current_period_label": current_label,
        "prior_period_label": prior_label,
        "current_period_column": current_column,
        "prior_period_column": prior_column,
    }

def map_table_cells_to_statement(company_name, report_type, date, table_cells, ticker="TBD"):
    """
    Maps normalized table cells into a validated FinancialStatement domain model.

    Processes extracted table cells from any engine (Docling, Azure, etc.), classifies 
    statement types and line items, infers column periods, cleans values using cleaners,
    and constructs FinancialLineItem objects conforming to the Golden Standard schema.

    Args:
        company_name (str): Name of the entity (e.g., 'Apple Inc.').
        report_type (str): Type of filing (e.g., '10-K' or '10-Q').
        date (str): The period ending date for the statement.
        table_cells (list): Normalized table cells with 'row', 'column', and 'text' keys.
        ticker (str): Stock ticker symbol (default: 'TBD').

    Returns:
        models.schemas.FinancialStatement: A fully validated Pydantic object 
            ready for downstream processing.
    """
    log_event(
        LOGGER,
        logging.INFO,
        "mapper_started",
        company_name=company_name,
        report_type=report_type,
        period_ending=date,
        table_cells=len(table_cells or []),
        ticker=ticker,
    )

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

    inferred_statement_type = None
    inferred_period_roles = _infer_period_column_roles(rows)

    for row_idx in sorted(rows.keys()):
        row = rows[row_idx]
        if 0 not in row:
            continue

        label_text = (row[0] or "").strip()

        row_statement_type = _classify_statement_type(label_text)
        if row_statement_type is not None:
            inferred_statement_type = row_statement_type
            continue

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

        row_level_statement_type = _infer_statement_type_from_label_rules(label_text)
        effective_statement_type = row_level_statement_type or inferred_statement_type

        primary_column = value_columns[0]
        period_values = _resolve_period_values(value_columns, inferred_period_roles)
        canonical_label = _classify_canonical_label(label_text, effective_statement_type)
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
            normalized_label=canonical_label,
            statement_type=effective_statement_type,
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
            current_period_value=period_values["current_period_value"],
            prior_period_value=period_values["prior_period_value"],
            current_period_label=period_values["current_period_label"],
            prior_period_label=period_values["prior_period_label"],
            current_period_column=period_values["current_period_column"],
            prior_period_column=period_values["prior_period_column"],
        )
        line_items.append(item)

    statement = FinancialStatement(
        company_name=company_name,
        ticker=ticker,
        report_type=report_type,
        period_ending=date,
        items=line_items
    )

    log_event(
        LOGGER,
        logging.INFO,
        "mapper_completed",
        company_name=company_name,
        items=len(statement.items),
        inferred_statement_type=inferred_statement_type,
    )

    return statement


def map_azure_table_to_statement(company_name, report_type, date, azure_table_cells):
    """Backward-compatible adapter for mapping Azure-style normalized table cells."""
    return map_table_cells_to_statement(
        company_name=company_name,
        report_type=report_type,
        date=date,
        table_cells=azure_table_cells,
    )