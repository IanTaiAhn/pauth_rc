from pydantic import BaseModel
from typing import Optional, List

class EvidenceItem(BaseModel):
    found: bool
    evidence_text: Optional[str] = None
    value: Optional[str] = None
    confidence: float

class PARequirements(BaseModel):
    conservative_therapy: EvidenceItem
    duration_documented: EvidenceItem
    failed_treatments: EvidenceItem
    symptom_severity: EvidenceItem
    recent_imaging: EvidenceItem

class MissingItem(BaseModel):
    name: str
    severity: str  # "high" | "medium"
    suggestion: str

class PAReadinessReport(BaseModel):
    score: int
    requirements: PARequirements
    missing_items: List[MissingItem]
    justification_text: str

# This schema is your product.

