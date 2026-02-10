from pydantic import BaseModel
from typing import Any, Dict, List


class PatientEvidence(BaseModel):
    data: Dict[str, Any]


class PolicyCriteria(BaseModel):
    data: Dict[str, Any]


class AuthzRequest(BaseModel):
    patient_evidence: PatientEvidence
    policy_criteria: PolicyCriteria


class RuleResult(BaseModel):
    rule_id: str
    description: str
    met: bool

class AuthzResponse(BaseModel):
    results: List[RuleResult]
    all_criteria_met: bool

class InitialPatientExtraction(BaseModel):
    filename: str
    score: float | int
    requirements: dict
    missing_items: list[str]