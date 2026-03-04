from dataclasses import dataclass
from typing import Optional

@dataclass
class AggregatedMetric:
	normalized_label: str
	value: Optional[float]
	unit: Optional[float] = None
	source_label: Optional[str] = None
	statement_type: Optional[str] = None
