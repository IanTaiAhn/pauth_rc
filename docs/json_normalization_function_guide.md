# Integration Guide for Your Existing System

## ✅ YES, it works with your JSON formats!

The rules engine **works perfectly** with your patient chart and insurance policy JSONs. I've created custom normalization functions specifically for your data structures.

## Quick Integration Steps

### 1. Replace Your Current Files

Replace these files in your backend:

```
backend/app/rules/rule_engine.py          → Use the new rule_engine.py
backend/app/normalization/normalize.py    → Replace with normalize_custom.py
backend/app/routes/authz.py               → Update to use new functions
```

### 2. Update Your Imports

In `authz.py`:

```python
# OLD
from backend.app.normalization.normalize_patient_evidence import normalize_patient_evidence
from backend.app.normalization.normalize_policy_criteria import normalize_policy_criteria

# NEW
from backend.app.normalization.normalize_custom import (
    normalize_patient_evidence,
    normalize_policy_criteria_manual  # Use this for full control
)
```

### 3. Choose Your Approach

You have **two options** for defining rules:

#### Option A: Automatic Rule Extraction (Quick Start)
Let the system automatically extract rules from your policy JSON:

```python
from normalize_custom import normalize_policy_criteria

# Automatically extracts rules from prerequisites and documentation_requirements
policy_rules = normalize_policy_criteria(request.policy_criteria.data)
```

**Pros:** Quick, works out of the box
**Cons:** Limited to what can be auto-detected from policy text

#### Option B: Manual Rule Definition (Recommended)
Explicitly define your rules for each insurance policy:

```python
from normalize_custom import normalize_policy_criteria_manual

# Define exactly what Aetna requires for CPT 73721
aetna_73721_rules = [
    {
        "id": "imaging_timeframe",
        "description": "X-ray within 60 days",
        "logic": "all",
        "conditions": [
            {"field": "imaging_documented", "operator": "eq", "value": True},
            {"field": "imaging_type", "operator": "eq", "value": "X-ray"},
            {"field": "imaging_months_ago", "operator": "lte", "value": 2}
        ]
    },
    {
        "id": "pt_minimum",
        "description": "PT at least 6 weeks",
        "logic": "all",
        "conditions": [
            {"field": "pt_attempted", "operator": "eq", "value": True},
            {"field": "pt_duration_weeks", "operator": "gte", "value": 6}
        ]
    },
    # ... more rules
]

policy_rules = normalize_policy_criteria_manual(request.policy_criteria.data, aetna_73721_rules)
```

**Pros:** Full control, explicit, testable
**Cons:** Requires manual rule creation per policy

### 4. Update Your API Response

Your response format changes slightly:

**OLD:**
```json
{
  "results": [
    {"rule_id": "...", "description": "...", "met": true}
  ],
  "all_criteria_met": true
}
```

**NEW (Enhanced):**
```json
{
  "results": [
    {
      "rule_id": "...",
      "description": "...",
      "met": true,
      "logic": "all",
      "condition_details": [
        {
          "condition": "pt_duration_weeks gte 6",
          "patient_value": 12,
          "met": true
        }
      ]
    }
  ],
  "all_criteria_met": true,
  "total_rules": 6,
  "rules_met": 6,
  "rules_failed": 0
}
```

## Example: Complete Integration

Here's a complete example for your FastAPI endpoint:

```python
from fastapi import APIRouter, HTTPException
from backend.app.models.schemas import AuthzRequest, AuthzResponse, RuleResult
from backend.app.normalization.normalize_custom import (
    normalize_patient_evidence,
    normalize_policy_criteria_manual
)
from backend.app.rules.rule_engine import evaluate_all

router = APIRouter()


# Define your insurance policy rules
POLICY_RULES = {
    "Aetna_73721": [
        {
            "id": "imaging_timeframe",
            "description": "X-ray must be within 60 days (2 months)",
            "logic": "all",
            "conditions": [
                {"field": "imaging_documented", "operator": "eq", "value": True},
                {"field": "imaging_type", "operator": "eq", "value": "X-ray"},
                {"field": "imaging_months_ago", "operator": "lte", "value": 2}
            ]
        },
        {
            "id": "pt_minimum_duration",
            "description": "Physical therapy must be at least 6 weeks",
            "logic": "all",
            "conditions": [
                {"field": "pt_attempted", "operator": "eq", "value": True},
                {"field": "pt_duration_weeks", "operator": "gte", "value": 6}
            ]
        },
        {
            "id": "medication_trial",
            "description": "NSAID trial must be documented and failed",
            "logic": "all",
            "conditions": [
                {"field": "nsaid_documented", "operator": "eq", "value": True},
                {"field": "nsaid_failed", "operator": "eq", "value": True}
            ]
        },
        {
            "id": "symptom_duration",
            "description": "Symptoms must persist for at least 3 months",
            "logic": "all",
            "conditions": [
                {"field": "symptom_duration_months", "operator": "gte", "value": 3}
            ]
        },
        {
            "id": "functional_impairment",
            "description": "Functional impairment must be documented",
            "logic": "all",
            "conditions": [
                {"field": "functional_impairment_documented", "operator": "eq", "value": True}
            ]
        },
        {
            "id": "data_quality",
            "description": "Evidence must be validated with no hallucinations",
            "logic": "all",
            "conditions": [
                {"field": "validation_passed", "operator": "eq", "value": True},
                {"field": "hallucinations_detected", "operator": "eq", "value": 0}
            ]
        }
    ]
}


@router.post("/evaluate", response_model=AuthzResponse)
async def evaluate_prior_auth(request: AuthzRequest):
    """
    Evaluate prior authorization request.
    """
    try:
        # Step 1: Normalize patient evidence
        patient_norm = normalize_patient_evidence(request.patient_evidence.data)
        
        # Step 2: Get rules for this payer/CPT
        policy_data = request.policy_criteria.data
        payer = policy_data.get("rules", {}).get("payer", "Unknown")
        cpt_code = policy_data.get("rules", {}).get("cpt_code", "Unknown")
        
        rule_key = f"{payer}_{cpt_code}"
        policy_rules = POLICY_RULES.get(rule_key)
        
        if not policy_rules:
            # Fallback to automatic extraction
            from normalize_custom import normalize_policy_criteria
            policy_rules = normalize_policy_criteria(policy_data)
        
        # Step 3: Evaluate
        evaluation = evaluate_all(patient_norm, policy_rules)
        
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
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation error: {str(e)}"
        )
```

## Testing Your Integration

Run the test file to verify everything works:

```bash
python test_your_json.py
```

Expected output:
- ✅ APPROVED (your patient passes all criteria)
- Detailed breakdown of each rule
- Shows patient values for each condition

## Common Customizations

### Add More Fields to Patient Normalization

In `normalize_custom.py`, add more fields as needed:

```python
def normalize_patient_evidence(evidence: dict) -> dict:
    # ... existing code ...
    
    # Add custom fields
    normalized["patient_age"] = evidence.get("patient_age")
    normalized["bmi"] = evidence.get("bmi")
    
    return normalized
```

### Add More Rule Types

Add new rules to `POLICY_RULES`:

```python
{
    "id": "age_requirement",
    "description": "Patient must be 18-65 years old",
    "logic": "all",
    "conditions": [
        {"field": "patient_age", "operator": "gte", "value": 18},
        {"field": "patient_age", "operator": "lte", "value": 65}
    ]
}
```

### Handle Multiple Payers

Create rule sets for each payer/CPT combination:

```python
POLICY_RULES = {
    "Aetna_73721": [...],
    "Aetna_73722": [...],
    "UnitedHealthcare_73721": [...],
    "BCBS_73721": [...]
}
```

## Available Fields from Your Patient Data

After normalization, you have access to:

```python
{
    "symptom_duration_months": int,
    "symptom_duration_weeks": int,
    "pt_attempted": bool,
    "pt_duration_weeks": int,
    "nsaid_documented": bool,
    "nsaid_outcome": str,
    "nsaid_failed": bool,
    "injection_documented": bool,
    "injection_outcome": str or None,
    "injection_failed": bool,
    "imaging_documented": bool,
    "imaging_type": str,
    "imaging_body_part": str,
    "imaging_months_ago": int,
    "functional_impairment_documented": bool,
    "functional_impairment_description": str,
    "validation_passed": bool,
    "hallucinations_detected": int,
    "score": int,
    "missing_items": list,
    "evidence_notes": list
}
```

## Next Steps

1. ✅ Test with your actual patient data
2. ✅ Define rules for all your payer/CPT combinations
3. ✅ Update your frontend to display detailed rule results
4. ✅ Add logging for audit trail
5. ✅ Create admin UI for managing rules

## Support

- Run `test_your_json.py` to verify integration
- Check `test_edge_cases.py` for handling missing data
- See `README.md` for full documentation