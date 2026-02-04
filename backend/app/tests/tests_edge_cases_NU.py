"""
Advanced usage examples and edge cases for the rules engine
"""

from rule_engine import evaluate_all
from normalize import normalize_patient_evidence, normalize_policy_criteria


# Edge Case 1: Missing data
incomplete_patient = {
    "diagnosis": ["M54.5"],
    # symptom_duration_weeks is missing
    # physical_therapy is missing
}

policy_with_missing = {
    "criteria": [
        {
            "id": "duration",
            "description": "6+ weeks symptoms",
            "requirement": {
                "symptom_duration_weeks": {"min": 6}
            }
        }
    ]
}

# Edge Case 2: Multiple diagnosis codes, need ANY match
patient_multiple_dx = {
    "diagnoses": ["M54.5", "M99.03", "Z98.89"],
    "symptom_duration_weeks": 8
}

policy_any_dx = {
    "criteria": [
        {
            "id": "qualifying_dx",
            "description": "Must have one of these diagnoses",
            "requirement": {
                "diagnosis_includes": ["M51.26", "M54.5", "M54.16"]
            }
        }
    ]
}

# Edge Case 3: Complex OR logic
patient_partial_treatment = {
    "diagnoses": ["M54.5"],
    "symptom_duration_weeks": 8,
    "pt_completed_weeks": 3,  # Not enough PT
    "nsaid_trial": True,      # But has tried NSAIDs
    "nsaid_failed": True
}

policy_flexible = {
    "criteria": [
        {
            "id": "duration",
            "description": "6+ weeks symptoms",
            "requirement": {
                "symptom_duration_weeks": {"min": 6}
            }
        },
        {
            "id": "conservative_care",
            "description": "Must complete PT OR fail NSAID trial",
            "logic": "any",  # At least ONE of these must pass
            "requirement": {
                "physical_therapy_weeks": {"min": 6},
                "nsaid_failed": True
            }
        }
    ]
}

# Edge Case 4: Range checks
patient_age_specific = {
    "diagnoses": ["M54.5"],
    "age": 45,
    "symptom_duration_weeks": 8
}

policy_age_restricted = {
    "criteria": [
        {
            "id": "age_range",
            "description": "Patient must be between 18 and 65",
            "requirement": {
                "age": {"min": 18, "max": 65}
            }
        }
    ]
}

# Edge Case 5: Nested conditions with custom fields
patient_complex = {
    "patient_id": "12345",
    "diagnoses": ["M54.5"],
    "symptom_duration_weeks": 12,
    "treatments": {
        "physical_therapy": {
            "completed": True,
            "weeks": 8,
            "progress": "minimal"
        },
        "medications": {
            "nsaids": {
                "tried": True,
                "failed": True
            },
            "muscle_relaxants": {
                "tried": True,
                "failed": False
            }
        }
    },
    "functional_status": {
        "oswestry_score": 45,  # Higher = worse disability
        "work_status": "modified_duty"
    }
}

# Custom normalization for complex structure
def normalize_complex_patient(evidence: dict) -> dict:
    normalized = {}
    
    normalized["diagnoses"] = evidence.get("diagnoses", [])
    normalized["symptom_duration_weeks"] = evidence.get("symptom_duration_weeks")
    normalized["age"] = evidence.get("age")
    
    # Handle nested treatment data
    if "treatments" in evidence:
        treatments = evidence["treatments"]
        
        if "physical_therapy" in treatments:
            pt = treatments["physical_therapy"]
            normalized["pt_completed_weeks"] = pt.get("weeks")
            normalized["pt_progress"] = pt.get("progress")
        
        if "medications" in treatments:
            meds = treatments["medications"]
            normalized["nsaid_failed"] = meds.get("nsaids", {}).get("failed", False)
            normalized["muscle_relaxant_failed"] = meds.get("muscle_relaxants", {}).get("failed", False)
    
    # Handle functional status
    if "functional_status" in evidence:
        func = evidence["functional_status"]
        normalized["oswestry_score"] = func.get("oswestry_score")
        normalized["work_status"] = func.get("work_status")
    
    return normalized

policy_complex = {
    "criteria": [
        {
            "id": "severity",
            "description": "Severe disability (Oswestry > 40)",
            "requirement": {
                "oswestry_score": {"min": 40}
            }
        },
        {
            "id": "failed_conservative",
            "description": "Failed multiple conservative treatments",
            "logic": "all",
            "requirement": {
                "physical_therapy_weeks": {"min": 6},
                "nsaid_failed": True
            }
        }
    ]
}


def run_edge_case_tests():
    print("=" * 80)
    print("EDGE CASE TESTS")
    print("=" * 80)
    
    # Test 1: Missing data
    print("\n[TEST 1] Missing patient data")
    print("-" * 80)
    patient_1 = normalize_patient_evidence(incomplete_patient)
    rules_1 = normalize_policy_criteria(policy_with_missing)
    result_1 = evaluate_all(patient_1, rules_1)
    
    print(f"Patient has symptom_duration_weeks: {patient_1.get('symptom_duration_weeks')}")
    print(f"Result: {'APPROVED' if result_1['all_criteria_met'] else 'DENIED'}")
    for r in result_1['results']:
        print(f"  [{r['met']}] {r['description']}")
    
    # Test 2: Multiple diagnoses
    print("\n[TEST 2] Multiple diagnoses - need ANY match")
    print("-" * 80)
    patient_2 = normalize_patient_evidence(patient_multiple_dx)
    rules_2 = normalize_policy_criteria(policy_any_dx)
    result_2 = evaluate_all(patient_2, rules_2)
    
    print(f"Patient diagnoses: {patient_2['diagnoses']}")
    print(f"Required (any of): {rules_2[0]['conditions'][0]['value']}")
    print(f"Result: {'APPROVED' if result_2['all_criteria_met'] else 'DENIED'}")
    
    # Test 3: OR logic with partial completion
    print("\n[TEST 3] OR logic - PT incomplete BUT NSAID failed")
    print("-" * 80)
    patient_3 = normalize_patient_evidence(patient_partial_treatment)
    rules_3 = normalize_policy_criteria(policy_flexible)
    result_3 = evaluate_all(patient_3, rules_3)
    
    print(f"PT weeks: {patient_3['pt_completed_weeks']} (need 6)")
    print(f"NSAID failed: {patient_3['nsaid_failed']}")
    print(f"Result: {'APPROVED' if result_3['all_criteria_met'] else 'DENIED'}")
    
    for r in result_3['results']:
        print(f"\n  [{r['met']}] {r['rule_id']}: {r['description']}")
        if 'condition_details' in r:
            for detail in r['condition_details']:
                status = "✓" if detail['met'] else "✗"
                print(f"      {status} {detail['condition']} (value: {detail['patient_value']})")
    
    # Test 4: Age range
    print("\n[TEST 4] Age range validation")
    print("-" * 80)
    patient_4 = normalize_patient_evidence(patient_age_specific)
    rules_4 = normalize_policy_criteria(policy_age_restricted)
    result_4 = evaluate_all(patient_4, rules_4)
    
    print(f"Patient age: {patient_4['age']}")
    print(f"Result: {'APPROVED' if result_4['all_criteria_met'] else 'DENIED'}")
    
    # Test 5: Complex nested structure
    print("\n[TEST 5] Complex nested structure with custom normalization")
    print("-" * 80)
    patient_5 = normalize_complex_patient(patient_complex)
    rules_5 = normalize_policy_criteria(policy_complex)
    result_5 = evaluate_all(patient_5, rules_5)
    
    print("Normalized patient data:")
    for key, value in patient_5.items():
        print(f"  {key}: {value}")
    
    print(f"\nResult: {'APPROVED' if result_5['all_criteria_met'] else 'DENIED'}")
    print(f"Rules met: {result_5['rules_met']}/{result_5['total_rules']}")
    
    for r in result_5['results']:
        print(f"\n  [{'✓' if r['met'] else '✗'}] {r['rule_id']}: {r['description']}")
        if 'condition_details' in r:
            for detail in r['condition_details']:
                status = "✓" if detail['met'] else "✗"
                print(f"      {status} {detail['condition']} (value: {detail['patient_value']})")


if __name__ == "__main__":
    run_edge_case_tests()