"""
FastAPI router for JSON normalization endpoints.

This module provides endpoints to normalize patient chart JSON and insurance policy JSON
into standardized formats suitable for rule evaluation.
"""

from fastapi import APIRouter, HTTPException
from app.api_models.schemas import (
    NormalizePatientRequest,
    NormalizePolicyRequest,
    NormalizeBothRequest,
    NormalizedPatientResponse,
    NormalizedPolicyResponse,
    NormalizeBothResponse,
    PolicyRule,
    RuleCondition
)
from app.normalization.normalized_custom import (
    normalize_patient_evidence,
    normalize_policy_criteria
)

router = APIRouter()


@router.post("/normalize/patient", response_model=NormalizedPatientResponse)
async def normalize_patient(request: NormalizePatientRequest):
    """
    Normalize patient chart JSON to canonical format.

    Takes raw patient evidence JSON (from Groq chart extraction) and converts it to a
    flat dictionary with standardized field names suitable for rule evaluation.

    **Example Input:**
    ```json
    {
      "patient_evidence": {
        "filename": "mocked_patient_pass.txt",
        "score": 100,
        "requirements": {
          "symptom_duration_months": 4,
          "conservative_therapy": {
            "physical_therapy": {
              "attempted": true,
              "duration_weeks": 8,
              "outcome": "failed"
            }
          },
          "_metadata": {
            "hallucinations_detected": 0,
            "validation_passed": true
          }
        },
        "missing_items": []
      }
    }
    ```

    **Example Output:**
    ```json
    {
      "normalized_data": {
        "symptom_duration_months": 4,
        "symptom_duration_weeks": 16,
        "pt_attempted": true,
        "pt_duration_weeks": 8,
        "validation_passed": true,
        "hallucinations_detected": 0
      },
      "metadata": {
        "fields_extracted": 6,
        "source": "patient_chart",
        "validation_passed": true,
        "hallucinations_detected": 0
      }
    }
    ```
    """
    try:
        # Normalize the patient evidence
        normalized_data = normalize_patient_evidence(request.patient_evidence)

        # Generate metadata
        metadata = {
            "fields_extracted": len(normalized_data),
            "source": "patient_chart",
            "validation_passed": normalized_data.get("validation_passed", False),
            "hallucinations_detected": normalized_data.get("hallucinations_detected", 0)
        }

        return NormalizedPatientResponse(
            normalized_data=normalized_data,
            metadata=metadata
        )

    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required field in patient evidence: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value in patient evidence: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error normalizing patient evidence: {str(e)}"
        )


@router.post("/normalize/policy", response_model=NormalizedPolicyResponse)
async def normalize_policy(request: NormalizePolicyRequest):
    """
    Normalize insurance policy JSON to rule format.

    Takes raw policy criteria JSON (from RAG pipeline) and converts it to a list of
    structured rules with conditions for evaluation.

    **Example Input:**
    ```json
    {
      "policy_criteria": {
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
      }
    }
    ```

    **Example Output:**
    ```json
    {
      "rules": [
        {
          "id": "xray_requirement",
          "description": "Weight-bearing X-rays must be completed within 60 days",
          "logic": "all",
          "conditions": [
            {"field": "imaging_documented", "operator": "eq", "value": true},
            {"field": "imaging_type", "operator": "eq", "value": "X-ray"},
            {"field": "imaging_months_ago", "operator": "lte", "value": 2}
          ]
        }
      ],
      "metadata": {
        "rules_extracted": 1,
        "payer": "Aetna",
        "cpt_code": "73721"
      }
    }
    ```
    """
    try:
        # Normalize the policy criteria
        rules_list = normalize_policy_criteria(request.policy_criteria)

        # Convert to Pydantic models
        policy_rules = []
        for rule in rules_list:
            conditions = [
                RuleCondition(
                    field=cond["field"],
                    operator=cond["operator"],
                    value=cond["value"]
                )
                for cond in rule.get("conditions", [])
            ]

            policy_rules.append(PolicyRule(
                id=rule["id"],
                description=rule["description"],
                logic=rule.get("logic", "all"),
                conditions=conditions
            ))

        # Generate metadata
        rules_data = request.policy_criteria.get("rules", {})
        metadata = {
            "rules_extracted": len(policy_rules),
            "source": "insurance_policy",
            "payer": rules_data.get("payer"),
            "cpt_code": rules_data.get("cpt_code")
        }

        return NormalizedPolicyResponse(
            rules=policy_rules,
            metadata=metadata
        )

    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required field in policy criteria: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value in policy criteria: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error normalizing policy criteria: {str(e)}"
        )


@router.post("/normalize/both", response_model=NormalizeBothResponse)
async def normalize_both(request: NormalizeBothRequest):
    """
    Normalize both patient evidence and policy criteria in a single request.

    This is a convenience endpoint that normalizes both datasets together, which can
    be useful when preparing data for rule evaluation.

    **Example Input:**
    ```json
    {
      "patient_evidence": {
        "filename": "patient_chart.txt",
        "score": 100,
        "requirements": {
          "symptom_duration_months": 4,
          "conservative_therapy": {
            "physical_therapy": {"attempted": true, "duration_weeks": 8}
          },
          "_metadata": {
            "hallucinations_detected": 0,
            "validation_passed": true
          }
        },
        "missing_items": []
      },
      "policy_criteria": {
        "rules": {
          "payer": "Aetna",
          "coverage_criteria": {
            "prerequisites": ["X-ray within 60 days"]
          }
        }
      }
    }
    ```

    **Example Output:**
    ```json
    {
      "normalized_patient": {
        "symptom_duration_months": 4,
        "pt_attempted": true
      },
      "normalized_policy": [
        {
          "id": "xray_requirement",
          "description": "X-ray must be completed within 60 days",
          "logic": "all",
          "conditions": [...]
        }
      ],
      "metadata": {
        "patient_fields_extracted": 2,
        "policy_rules_extracted": 1
      }
    }
    ```
    """
    try:
        # Normalize patient evidence
        normalized_patient = normalize_patient_evidence(request.patient_evidence)

        # Normalize policy criteria
        rules_list = normalize_policy_criteria(request.policy_criteria)

        # Convert to Pydantic models
        normalized_policy = []
        for rule in rules_list:
            conditions = [
                RuleCondition(
                    field=cond["field"],
                    operator=cond["operator"],
                    value=cond["value"]
                )
                for cond in rule.get("conditions", [])
            ]

            normalized_policy.append(PolicyRule(
                id=rule["id"],
                description=rule["description"],
                logic=rule.get("logic", "all"),
                conditions=conditions
            ))

        # Generate combined metadata
        rules_data = request.policy_criteria.get("rules", {})
        metadata = {
            "patient_fields_extracted": len(normalized_patient),
            "policy_rules_extracted": len(normalized_policy),
            "patient_validation_passed": normalized_patient.get("validation_passed", False),
            "patient_hallucinations_detected": normalized_patient.get("hallucinations_detected", 0),
            "policy_payer": rules_data.get("payer"),
            "policy_cpt_code": rules_data.get("cpt_code")
        }

        return NormalizeBothResponse(
            normalized_patient=normalized_patient,
            normalized_policy=normalized_policy,
            metadata=metadata
        )

    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required field: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error normalizing data: {str(e)}"
        )
