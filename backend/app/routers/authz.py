from fastapi import APIRouter, HTTPException
from app.api_models.schemas import AuthzRequest, AuthzResponse, RuleResult
from fastapi.responses import StreamingResponse
import io
# from backend.app.normalization.normalize import normalize_patient_evidence, normalize_policy_criteria
# from backend.app.rules.rule_engine import evaluate_all
from app.rules.rule_engine import evaluate_all
from app.normalization.normalized_custom import (
    normalize_patient_evidence, 
    normalize_policy_criteria,
    # normalize_policy_criteria_manual
)
from app.utils.make_report import build_authz_report
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

    IMPROVED: Better validation and error handling for normalized JSON objects.
    """
    try:
        # Step 0: Validate input data
        if not request.patient_evidence.data:
            raise HTTPException(
                status_code=400,
                detail="Patient evidence data is empty"
            )

        if not request.policy_criteria.data:
            raise HTTPException(
                status_code=400,
                detail="Policy criteria data is empty"
            )

        # Step 1: Normalize patient evidence
        try:
            patient_norm = normalize_patient_evidence(request.patient_evidence.data)
        except Exception as e:
            print(f"Error normalizing patient evidence: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=400,
                detail=f"Failed to normalize patient evidence: {str(e)}"
            )

        # Step 2: Normalize policy criteria
        try:
            policy_rules = normalize_policy_criteria(request.policy_criteria.data)
        except Exception as e:
            print(f"Error normalizing policy criteria: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=400,
                detail=f"Failed to normalize policy criteria: {str(e)}"
            )

        # Validate that we have rules
        if not policy_rules:
            raise HTTPException(
                status_code=400,
                detail="No rules could be extracted from policy criteria"
            )

        # Step 3: Run rule engine
        try:
            evaluation = evaluate_all(patient_norm, policy_rules)
        except Exception as e:
            print(f"Error evaluating rules: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to evaluate rules: {str(e)}"
            )

        # Step 4: Format response
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

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
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
        print(f"Unexpected evaluation error: {str(e)}")
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Unexpected evaluation error: {str(e)}"
        )
    


@router.post("/compare_json_objects/report")
async def evaluate_prior_auth_report(request: AuthzRequest):
    """
    Generate a detailed prior authorization evaluation report.

    IMPROVED: Better error handling and validation of normalized data.
    """
    try:
        # Step 1: Validate input data
        if not request.patient_evidence.data:
            raise HTTPException(
                status_code=400,
                detail="Patient evidence data is empty"
            )

        if not request.policy_criteria.data:
            raise HTTPException(
                status_code=400,
                detail="Policy criteria data is empty"
            )

        # Step 2: Normalize patient evidence
        try:
            patient_norm = normalize_patient_evidence(request.patient_evidence.data)
        except Exception as e:
            print(f"Error normalizing patient evidence: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=400,
                detail=f"Failed to normalize patient evidence: {str(e)}"
            )

        # Step 3: Normalize policy criteria
        try:
            policy_rules = normalize_policy_criteria(request.policy_criteria.data)
        except Exception as e:
            print(f"Error normalizing policy criteria: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=400,
                detail=f"Failed to normalize policy criteria: {str(e)}"
            )

        # Step 4: Validate that we have rules to evaluate
        if not policy_rules:
            raise HTTPException(
                status_code=400,
                detail="No rules could be extracted from policy criteria"
            )

        # Step 5: Evaluate rules
        try:
            evaluation = evaluate_all(patient_norm, policy_rules)
        except Exception as e:
            print(f"Error evaluating rules: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to evaluate rules: {str(e)}"
            )

        # Step 6: Build text report
        try:
            report_text = build_authz_report(patient_norm, policy_rules, evaluation)
        except Exception as e:
            print(f"Error building report: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to build report: {str(e)}"
            )

        # Step 7: Convert to file-like stream and return
        file_stream = io.BytesIO(report_text.encode("utf-8"))

        return StreamingResponse(
            file_stream,
            media_type="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=prior_auth_report.txt"
            },
        )

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        print(f"Unexpected error generating report: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error generating report: {str(e)}"
        )
