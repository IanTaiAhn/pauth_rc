"""
Test cases for the rules engine with example JSON structures
"""

from backend.app.rules.rule_engine import evaluate_all
from backend.app.normalization.normalize_custom import normalize_patient_evidence, normalize_policy_criteria


# Example 1: Patient chart with nested structure
patient_chart_1 = {
    "diagnosis": ["M54.5", "M51.26"],  # Low back pain, lumbar disc disorder
    "symptom_duration_weeks": 8,
    "conservative_therapy": {
        "physical_therapy": {
            "completed_weeks": 6,
            "sessions": 12
        },
        "nsaids": {
            "trialed": True,
            "outcome": "no relief"
        }
    },
    "imaging": {
        "mri": {
            "done": True,
            "months_ago": 2,
            "findings": "herniated disc L4-L5"
        }
    }
}

# Example 2: Policy criteria with multiple rules
policy_criteria_1 = {
    "criteria": [
        {
            "id": "symptom_duration",
            "description": "Patient must have symptoms for at least 6 weeks",
            "requirement": {
                "symptom_duration_weeks": {"min": 6}
            }
        },
        {
            "id": "diagnosis",
            "description": "Patient must have qualifying diagnosis",
            "requirement": {
                "diagnosis_includes": ["M54.5", "M51.26", "M51.16"]
            }
        },
        {
            "id": "conservative_care",
            "description": "Patient must complete 6 weeks of physical therapy",
            "requirement": {
                "physical_therapy_weeks": {"min": 6}
            }
        },
        {
            "id": "medication_trial",
            "description": "Patient must have failed NSAID trial",
            "logic": "all",
            "requirement": {
                "nsaid_trial_required": True,
                "nsaid_failed": True
            }
        }
    ]
}

# Example 3: Different patient chart format
patient_chart_2 = {
    "diagnoses": ["M51.26"],
    "symptoms": {
        "duration_weeks": 10
    },
    "physical_therapy": {
        "weeks": 8,
        "sessions": 16
    },
    "medications": ["ibuprofen", "acetaminophen"],
    "imaging": {
        "mri": {
            "done": True,
            "months_ago": 1
        }
    }
}

# Example 4: Simpler policy format
policy_criteria_2 = {
    "criteria": [
        {
            "id": "duration_check",
            "description": "Symptoms must persist for 6+ weeks",
            "requirement": {
                "symptom_duration_weeks": 6
            }
        },
        {
            "id": "therapy_check",
            "description": "Must complete physical therapy",
            "requirement": {
                "physical_therapy_weeks": 6
            }
        }
    ]
}


def run_tests():
    print("=" * 80)
    print("TEST 1: Full workflow with nested structure")
    print("=" * 80)
    
    # Normalize
    patient_norm_1 = normalize_patient_evidence(patient_chart_1)
    print("\nNormalized Patient Evidence:")
    for key, value in patient_norm_1.items():
        print(f"  {key}: {value}")
    
    policy_rules_1 = normalize_policy_criteria(policy_criteria_1)
    print("\nNormalized Policy Rules:")
    for rule in policy_rules_1:
        print(f"\n  Rule: {rule['id']}")
        print(f"  Description: {rule['description']}")
        print(f"  Logic: {rule['logic']}")
        print(f"  Conditions:")
        for cond in rule['conditions']:
            print(f"    - {cond['field']} {cond['operator']} {cond['value']}")
    
    # Evaluate
    results_1 = evaluate_all(patient_norm_1, policy_rules_1)
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS:")
    print("=" * 80)
    print(f"All criteria met: {results_1['all_criteria_met']}")
    print(f"Rules met: {results_1['rules_met']}/{results_1['total_rules']}")
    
    for result in results_1['results']:
        print(f"\n[{'✓' if result['met'] else '✗'}] {result['rule_id']}: {result['description']}")
        if 'condition_details' in result:
            for detail in result['condition_details']:
                status = "✓" if detail['met'] else "✗"
                print(f"    {status} {detail['condition']} (patient value: {detail['patient_value']})")
    
    print("\n" + "=" * 80)
    print("TEST 2: Alternative format")
    print("=" * 80)
    
    patient_norm_2 = normalize_patient_evidence(patient_chart_2)
    print("\nNormalized Patient Evidence:")
    for key, value in patient_norm_2.items():
        print(f"  {key}: {value}")
    
    policy_rules_2 = normalize_policy_criteria(policy_criteria_2)
    results_2 = evaluate_all(patient_norm_2, policy_rules_2)
    
    print("\nEVALUATION RESULTS:")
    print(f"All criteria met: {results_2['all_criteria_met']}")
    
    for result in results_2['results']:
        print(f"\n[{'✓' if result['met'] else '✗'}] {result['rule_id']}: {result['description']}")
        if 'condition_details' in result:
            for detail in result['condition_details']:
                status = "✓" if detail['met'] else "✗"
                print(f"    {status} {detail['condition']} (patient value: {detail['patient_value']})")


if __name__ == "__main__":
    run_tests()