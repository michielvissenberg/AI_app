import os
from dotenv import load_dotenv

# Import our modular parts
from models.schemas import FinancialLineItem, FinancialStatement
from processors.cleaners import clean_financial_value

def test_pipeline():
    print("--- Starting Smoke Test ---")
    
    load_dotenv()
    print(f"Env Loaded: {'Yes' if os.getenv('AZURE_KEY') else 'No (Wait for credits)'}")

    raw_value = "$1,250.50"
    cleaned = clean_financial_value(raw_value)
    
    try:
        test_item = FinancialLineItem(label="Test Asset", value=cleaned)
        report = FinancialStatement(
            company_name="Test Corp",
            ticker="TST",
            report_type="10-K",
            period_ending="2026-01-01",
            items=[test_item]
        )
        print(f"Success! Pydantic validated: {report.company_name} - {report.items[0].value}")
    except Exception as e:
        print(f"Validation Error: {e}")

if __name__ == "__main__":
    test_pipeline()