from models.schemas import FinancialLineItem, FinancialStatement
from cleaners import clean_financial_value, normalize_label

def map_azure_table_to_statement(company_name, report_type, date, azure_table_cells):
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
    for cell in azure_table_cells:
        if cell['row'] not in rows:
            rows[cell['row']] = {}
        rows[cell['row']][cell['column']] = cell['text']

    for row_idx in sorted(rows.keys()):
        row = rows[row_idx]
        # Usually: Col 0 is the Label, Col 1 is the Value
        if 0 in row and 1 in row:
            label_text = row[0]
            value_text = row[1]
            
            # Create the Pydantic item (Validation happens here!)
            item = FinancialLineItem(
                label=label_text,
                normalized_label=normalize_label(label_text),
                value=clean_financial_value(value_text)
            )
            line_items.append(item)

    return FinancialStatement(
        company_name=company_name,
        ticker="TBD", # We can add logic to find this
        report_type=report_type,
        period_ending=date,
        items=line_items
    )