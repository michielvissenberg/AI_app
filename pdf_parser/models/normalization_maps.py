SCALE_TOKEN_MAP = {
    "k": "thousands",
    "thousand": "thousands",
    "thousands": "thousands",
    "m": "millions",
    "mm": "millions",
    "mn": "millions",
    "million": "millions",
    "millions": "millions",
    "b": "billions",
    "bn": "billions",
    "billion": "billions",
    "billions": "billions",
}


REVENUE_LABEL_MAP = {
    "revenue": "revenue",
    "revenues": "revenue",
    "total_revenue": "revenue",
    "total_revenues": "revenue",
    "net_revenue": "revenue",
    "net_revenues": "revenue",
    "sales": "revenue",
    "net_sales": "revenue",
    "total_sales": "revenue",
    "total_net_sales": "revenue",
}

NET_INCOME_LABEL_MAP = {
    "net_income": "net_income",
    "net_earnings": "net_income",
    "profit": "net_income",
    "net_profit": "net_income",
    "profit_for_the_year": "net_income",
    "income_for_the_year": "net_income",
}

GROSS_PROFIT_LABEL_MAP = {
    "gross_profit": "gross_profit",
    "gross_margin": "gross_profit",
    "total_gross_margin": "gross_profit",
}

OPERATING_INCOME_LABEL_MAP = {
    "operating_income": "operating_income",
    "income_from_operations": "operating_income",
    "operating_profit": "operating_income",
    "operating_earnings": "operating_income",
    "ebit": "operating_income",
}

TOTAL_ASSETS_LABEL_MAP = {
    "total_assets": "total_assets",
    "assets_total": "total_assets",
}

TOTAL_LIABILITIES_LABEL_MAP = {
    "total_liabilities": "total_liabilities",
    "liabilities_total": "total_liabilities",
}

TOTAL_CURRENT_ASSETS_LABEL_MAP = {
    "total_current_assets": "total_current_assets",
    "current_assets_total": "total_current_assets",
}

TOTAL_CURRENT_LIABILITIES_LABEL_MAP = {
    "total_current_liabilities": "total_current_liabilities",
    "current_liabilities_total": "total_current_liabilities",
}

TOTAL_SHAREHOLDERS_EQUITY_LABEL_MAP = {
    "total_shareholders_equity": "total_shareholders_equity",
    "total_stockholders_equity": "total_shareholders_equity",
    "shareholders_equity": "total_shareholders_equity",
    "stockholders_equity": "total_shareholders_equity",
    "total_equity": "total_shareholders_equity",
}

CASH_AND_CASH_EQUIVALENTS_LABEL_MAP = {
    "cash_and_cash_equivalents": "cash_and_cash_equivalents",
    "cash_&_cash_equivalents": "cash_and_cash_equivalents",
    "cash_equivalents": "cash_and_cash_equivalents",
}

MARKETABLE_SECURITIES_LABEL_MAP = {
    "marketable_securities": "marketable_securities",
    "short_term_investments": "marketable_securities",
}

ACCOUNTS_RECEIVABLE_NET_LABEL_MAP = {
    "accounts_receivable_net": "accounts_receivable_net",
    "accounts_receivable": "accounts_receivable_net",
    "accounts_receivables": "accounts_receivable_net",
    "accounts_receivable,_net": "accounts_receivable_net",
    "trade_accounts_receivable": "accounts_receivable_net",
    "trade_accounts_receivable_net": "accounts_receivable_net",
    "trade_receivables": "accounts_receivable_net",
    "trade_receivables_net": "accounts_receivable_net",
    "receivables_net": "accounts_receivable_net",
}

NET_CASH_FROM_OPERATING_ACTIVITIES_LABEL_MAP = {
    "net_cash_from_operating_activities": "net_cash_from_operating_activities",
    "net_cash_provided_by_operating_activities": "net_cash_from_operating_activities",
    "net_cash_provided_by_operating_activities_gaap": "net_cash_from_operating_activities",
    "cash_generated_by_operating_activities": "net_cash_from_operating_activities",
    "net_cash_flows_from_operating_activities": "net_cash_from_operating_activities",
}

INTEREST_EXPENSE_LABEL_MAP = {
    "interest_expense": "interest_expense",
    "interest_expense_net": "interest_expense",
    "finance_costs": "interest_expense",
    "interest_and_other_expense": "interest_expense",
}

RETAINED_EARNINGS_LABEL_MAP = {
    "retained_earnings": "retained_earnings",
    "retained_earnings_accumulated_deficit": "retained_earnings",
    "accumulated_deficit": "retained_earnings",
    "accumulated_earnings": "retained_earnings",
}

NORMALIZED_LABEL_MAPS = [
    REVENUE_LABEL_MAP,
    NET_INCOME_LABEL_MAP,
    GROSS_PROFIT_LABEL_MAP,
    OPERATING_INCOME_LABEL_MAP,
    TOTAL_ASSETS_LABEL_MAP,
    TOTAL_LIABILITIES_LABEL_MAP,
    TOTAL_CURRENT_ASSETS_LABEL_MAP,
    TOTAL_CURRENT_LIABILITIES_LABEL_MAP,
    TOTAL_SHAREHOLDERS_EQUITY_LABEL_MAP,
    CASH_AND_CASH_EQUIVALENTS_LABEL_MAP,
    MARKETABLE_SECURITIES_LABEL_MAP,
    ACCOUNTS_RECEIVABLE_NET_LABEL_MAP,
    NET_CASH_FROM_OPERATING_ACTIVITIES_LABEL_MAP,
    INTEREST_EXPENSE_LABEL_MAP,
    RETAINED_EARNINGS_LABEL_MAP,
]
