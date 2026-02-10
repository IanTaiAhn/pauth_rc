from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


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

# ===== Normalization Schemas =====

class NormalizePatientRequest(BaseModel):
    """Request schema for normalizing patient evidence JSON."""
    patient_evidence: Dict[str, Any] = Field(
        ...,
        description="Raw patient chart JSON data to normalize",
        examples=[{
            "timestamp": "2026-01-27T16:32:19.123456",
            "analysis": {
                "requirements": {
                    "symptom_duration_months": 4,
                    "conservative_therapy": {
                        "physical_therapy": {
                            "attempted": True,
                            "duration_weeks": 8,
                            "outcome": "failed"
                        },
                        "nsaids": {
                            "documented": True,
                            "outcome": "failed"
                        }
                    },
                    "imaging": {
                        "documented": True,
                        "type": "X-ray",
                        "body_part": "shoulder",
                        "months_ago": 1
                    }
                }
            }
        }]
    )


class NormalizePolicyRequest(BaseModel):
    """Request schema for normalizing policy criteria JSON."""
    policy_criteria: Dict[str, Any] = Field(
        ...,
        description="Raw insurance policy JSON data to normalize",
        examples=[{
            "rules": {
                "payer": "Aetna",
                "cpt_code": "73721",
                "coverage_criteria": {
                    "prerequisites": [
                        "Weight-bearing X-rays within 60 days"
                    ],
                    "documentation_requirements": [
                        "Physical therapy documentation",
                        "Medication trial records"
                    ]
                }
            }
        }]
    )


class NormalizedPatientResponse(BaseModel):
    """Response schema for normalized patient evidence."""
    normalized_data: Dict[str, Any] = Field(
        ...,
        description="Normalized patient evidence in canonical format"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the normalization process"
    )


class RuleCondition(BaseModel):
    """A single condition within a rule."""
    field: str = Field(..., description="Field name to evaluate")
    operator: str = Field(..., description="Comparison operator (eq, ne, gt, gte, lt, lte, in, not_in, contains)")
    value: Any = Field(..., description="Value to compare against")


class PolicyRule(BaseModel):
    """A single policy rule with conditions."""
    id: str = Field(..., description="Unique rule identifier")
    description: str = Field(..., description="Human-readable rule description")
    logic: str = Field(default="all", description="Logic operator: 'all' (AND) or 'any' (OR)")
    conditions: List[RuleCondition] = Field(..., description="List of conditions to evaluate")


class NormalizedPolicyResponse(BaseModel):
    """Response schema for normalized policy criteria."""
    rules: List[PolicyRule] = Field(
        ...,
        description="List of normalized policy rules"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the normalization process"
    )


class NormalizeBothRequest(BaseModel):
    """Request schema for normalizing both patient evidence and policy criteria."""
    patient_evidence: Dict[str, Any] = Field(
        ...,
        description="Raw patient chart JSON data"
    )
    policy_criteria: Dict[str, Any] = Field(
        ...,
        description="Raw insurance policy JSON data"
    )


class NormalizeBothResponse(BaseModel):
    """Response schema for normalizing both datasets."""
    normalized_patient: Dict[str, Any] = Field(
        ...,
        description="Normalized patient evidence"
    )
    normalized_policy: List[PolicyRule] = Field(
        ...,
        description="Normalized policy rules"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about both normalization processes"
    )
