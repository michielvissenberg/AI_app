from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime


class FinancialLineItem(BaseModel):
    """Canonical representation of a single extracted financial metric row."""
    label: str = Field(description="The exact name from the report, e.g., 'Total Revenue'")
    normalized_label: Optional[str] = Field(None, description="Standardized name, e.g., 'revenue'")
    statement_type: Optional[str] = Field(None, description="Inferred statement type, e.g., income_statement")
    value: Optional[float] = None
    unit: str = Field(default="USD")
    scale: str = Field(default="millions", description="e.g., millions, thousands")
    column_values: Optional[List[Optional[float]]] = None
    column_units: Optional[List[str]] = None
    column_scales: Optional[List[str]] = None
    column_parse_statuses: Optional[List[str]] = None
    parse_status: Optional[str] = None
    yoy_change: Optional[float] = None
    yoy_unit: Optional[str] = None
    current_period_value: Optional[float] = None
    prior_period_value: Optional[float] = None
    current_period_label: Optional[str] = None
    prior_period_label: Optional[str] = None
    current_period_column: Optional[int] = None
    prior_period_column: Optional[int] = None
    supplemental_metrics: Optional[Dict[str, List[Optional[float]]]] = None


class NormalizedTableCell(BaseModel):
    """Engine-agnostic normalized table cell with row/column coordinates."""
    row: int
    column: int
    text: str = ""


class NormalizedExtraction(BaseModel):
    """Top-level normalized extraction payload emitted by parsing engines."""
    cells: List[NormalizedTableCell]
    source_engine: Optional[str] = None


class FinancialStatement(BaseModel):
    """Validated financial statement entity assembled from normalized table rows."""
    company_name: str
    ticker: str
    report_type: str = Field(description="10-K or 10-Q")
    period_ending: str
    extracted_at: datetime = Field(default_factory=datetime.now)
    items: List[FinancialLineItem]
    
    summary_vector: Optional[List[float]] = None
