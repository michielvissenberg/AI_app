from typing import Any, Dict


RATIO_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "gross_margin": {
        "required_fields": ["gross_profit", "revenue"],
        "description": "Gross profit divided by revenue.",
    },
    "operating_margin": {
        "required_fields": ["operating_income", "revenue"],
        "description": "Operating income divided by revenue.",
    },
    "net_margin": {
        "required_fields": ["net_income", "revenue"],
        "description": "Net income divided by revenue.",
    },
    "current_ratio": {
        "required_fields": ["total_current_assets", "total_current_liabilities"],
        "description": "Current assets divided by current liabilities.",
    },
    "quick_ratio": {
        "required_fields": [
            "cash_and_cash_equivalents",
            "marketable_securities",
            "accounts_receivable_net",
            "total_current_liabilities",
        ],
        "description": "(Cash + marketable securities + accounts receivable) divided by current liabilities.",
    },
    "cash_ratio": {
        "required_fields": ["cash_and_cash_equivalents", "total_current_liabilities"],
        "description": "Cash and cash equivalents divided by current liabilities.",
    },
    "working_capital_to_assets": {
        "required_fields": ["total_current_assets", "total_current_liabilities", "total_assets"],
        "description": "(Current assets minus current liabilities) divided by total assets.",
    },
    "debt_to_equity": {
        "required_fields": ["total_liabilities", "total_shareholders_equity"],
        "description": "Total liabilities divided by shareholders' equity.",
    },
    "debt_to_assets": {
        "required_fields": ["total_liabilities", "total_assets"],
        "description": "Total liabilities divided by total assets.",
    },
    "equity_ratio": {
        "required_fields": ["total_shareholders_equity", "total_assets"],
        "description": "Shareholders' equity divided by total assets.",
    },
    "asset_turnover": {
        "required_fields": ["revenue", "total_assets"],
        "description": "Revenue divided by total assets.",
    },
    "return_on_assets": {
        "required_fields": ["net_income", "total_assets"],
        "description": "Net income divided by total assets.",
    },
    "return_on_equity": {
        "required_fields": ["net_income", "total_shareholders_equity"],
        "description": "Net income divided by shareholders' equity.",
    },
    "operating_cash_flow_margin": {
        "required_fields": ["net_cash_from_operating_activities", "revenue"],
        "description": "Net cash from operating activities divided by revenue.",
    },
    "operating_cash_flow_to_current_liabilities": {
        "required_fields": ["net_cash_from_operating_activities", "total_current_liabilities"],
        "description": "Net cash from operating activities divided by current liabilities.",
    },
    "cash_flow_to_debt": {
        "required_fields": ["net_cash_from_operating_activities", "total_liabilities"],
        "description": "Net cash from operating activities divided by total liabilities.",
    },
    "interest_coverage": {
        "required_fields": ["operating_income", "interest_expense"],
        "description": "Operating income divided by interest expense.",
    },
    "gross_profit_to_assets": {
        "required_fields": ["gross_profit", "total_assets"],
        "description": "Gross profit divided by total assets.",
    },
    "operating_return_on_assets": {
        "required_fields": ["operating_income", "total_assets"],
        "description": "Operating income divided by total assets.",
    },
    "retained_earnings_to_assets": {
        "required_fields": ["retained_earnings", "total_assets"],
        "description": "Retained earnings divided by total assets.",
    },
}
