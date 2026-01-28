from fastapi import APIRouter, HTTPException
from backend.app.models.schemas import AuthzRequest, AuthzResponse, RuleResult
from backend.app.normalization.normalize import normalize_patient_evidence, normalize_policy_criteria
from backend.app.rules.rule_engine import evaluate_all

router = APIRouter()


@router.post("/evaluate", response_model=AuthzResponse)
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