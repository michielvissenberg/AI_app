import re

def is_percentage_value(raw_value: str) -> bool:
    return "%" in (raw_value or "")


def clean_financial_value(raw_value: str):
    """
    Parses a string representing a financial amount into a float.

    This function handles common financial formatting:
    - Removes currency symbols ($) and whitespace.
    - Removes thousands-separator commas.
    - Converts accounting-style negative numbers ' (100.00) ' to ' -100.00 '.
    - Defaults to 0.0 if the string is empty or 'N/A'.

    Args:
        raw_value (str): The raw string extracted from a document cell.

    Returns:
        float: The cleaned numerical value.
    """
    if not raw_value:
        return None

    normalized = raw_value.strip().lower()
    if not normalized or normalized in {"n/a", "na", "-", "—", "–", "nm"}:
        return None
    
    # Remove currency symbols and commas
    clean_str = re.sub(r'[$,% ]', '', raw_value)
    
    # Handle negative numbers in parentheses: (100) -> -100
    if clean_str.startswith('(') and clean_str.endswith(')'):
        clean_str = '-' + clean_str[1:-1]
        
    try:
        return float(clean_str)
    except ValueError:
        return None
    
def normalize_label(label: str) -> str:
    """
    Standardizes a text label for programmatic use and search indexing.

    Cleaning steps:
    1. Trims leading/trailing whitespace.
    2. Converts all characters to lowercase.
    3. Replaces spaces with underscores.
    4. Removes trailing colons or special characters.

    Example: "Total Revenue: " -> "total_revenue"

    Args:
        label (str): The raw text label from the first column of a table.

    Returns:
        str: A slug-style normalized string.
    """
    return label.strip().lower().replace(" ", "_").replace(":", "")