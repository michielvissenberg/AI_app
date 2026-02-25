from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class FinancialLineItem(BaseModel):
    label: str = Field(description="The exact name from the report, e.g., 'Total Revenue'")
    normalized_label: Optional[str] = Field(None, description="Standardized name, e.g., 'revenue'")
    value: Optional[float] = None
    unit: str = Field(default="USD")
    scale: str = Field(default="millions", description="e.g., millions, thousands")

class FinancialStatement(BaseModel):
    company_name: str
    ticker: str
    report_type: str = Field(description="10-K or 10-Q")
    period_ending: str
    extracted_at: datetime = Field(default_factory=datetime.now)
    items: List[FinancialLineItem]
    
    summary_vector: Optional[List[float]] = None
