from fastapi import APIRouter, HTTPException
from backend.app.models.schemas import AuthzRequest, AuthzResponse, RuleResult
from fastapi.responses import StreamingResponse
import io
# from backend.app.normalization.normalize import normalize_patient_evidence, normalize_policy_criteria
# from backend.app.rules.rule_engine import evaluate_all
from backend.app.rules.rule_engine import evaluate_all
from backend.app.normalization.normalized_custom import (
    normalize_patient_evidence, 
    normalize_policy_criteria,
    # normalize_policy_criteria_manual
)
from backend.app.utils.make_report import build_authz_report
# import json

router = APIRouter()


@router.post("/compare_json_objects", response_model=AuthzResponse)
async def evaluate_prior_auth(request: AuthzRequest):
    """
    Evaluate prior authorization request against policy criteria.
    
    Process:
    1. Normalize patient evidence to canonical format
    2. Normalize policy criteria to rule format
    3. Evaluate all rules against patient data
    4. Return detailed results
    """
    try:
        # Step 1 — Normalize patient evidence
        patient_norm = normalize_patient_evidence(request.patient_evidence.data)
        
        # Step 2 — Normalize policy criteria
        policy_rules = normalize_policy_criteria(request.policy_criteria.data)
        
        # Step 3 — Run rule engine
        evaluation = evaluate_all(patient_norm, policy_rules)
        
        # Step 4 — Format response
        results = [
            RuleResult(
                rule_id=r["rule_id"],
                description=r["description"],
                met=r["met"]
            )
            for r in evaluation["results"]
        ]
        
        return AuthzResponse(
            results=results,
            all_criteria_met=evaluation["all_criteria_met"]
        )
    
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required field in input: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value in input: {str(e)}"
        )
    except Exception as e:
        # Log the full error for debugging
        print(f"Evaluation error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation error: {str(e)}"
        )
    


@router.post("/compare_json_objects/report")
async def evaluate_prior_auth_report(request: AuthzRequest):
    try:
        # Normalize
        patient_norm = normalize_patient_evidence(request.patient_evidence.data)
        policy_rules = normalize_policy_criteria(request.policy_criteria.data)

        # Evaluate
        evaluation = evaluate_all(patient_norm, policy_rules)

        # Build text report
        report_text = build_authz_report(patient_norm, policy_rules, evaluation)

        # Convert to file-like stream
        file_stream = io.BytesIO(report_text.encode("utf-8"))

        return StreamingResponse(
            file_stream,
            media_type="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=prior_auth_report.txt"
            },
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error generating report")
