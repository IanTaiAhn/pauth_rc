"""
Test with YOUR actual JSON formats
"""

from backend.app.rules.rule_engine import evaluate_all
from backend.app.normalization.normalized_custom import (
    normalize_patient_evidence, 
    normalize_policy_criteria,
    normalize_policy_criteria_manual
)
import json


# Your actual patient chart JSON
patient_chart = {
    "timestamp": "2026-01-27T16:32:19.659972",
    "analysis": {
        "filename": "mocked_pass.txt",
        "score": 100,
        "requirements": {
            "symptom_duration_months": 4,
            "conservative_therapy": {
                "physical_therapy": {
                    "attempted": True,
                    "duration_weeks": 12
                },
                "nsaids": {
                    "documented": True,
                    "outcome": "failed"
                },
                "injections": {
                    "documented": False,
                    "outcome": None
                }
            },
            "imaging": {
                "documented": True,
                "type": "X-ray",
                "body_part": "Right Knee",
                "months_ago": 1
            },
            "functional_impairment": {
                "documented": True,
                "description": "significant functional limitations affecting work and daily activities"
            },
            "evidence_notes": [
                "Patient has completed 8 weeks (56 days) of conservative management:",
                "Physical therapy: 2x weekly from 11/20/2024 to 01/10/2025",
                "Total sessions: 12 sessions completed",
                "Focus: Quadriceps strengthening, range of motion, modalities",
                "PT notes indicate patient compliant but persistent symptoms",
                "Despite 8 weeks of conservative care, patient continues to have significant functional limitations affecting work and daily activities."
            ],
            "_metadata": {
                "hallucinations_detected": 0,
                "hallucinated_notes": [],
                "validation_passed": True
            }
        },
        "missing_items": []
    }
}

# Your actual insurance policy JSON
policy_insurance = {
    "rules": {
        "payer": "Aetna",
        "cpt_code": "73721",
        "coverage_criteria": {
            "clinical_indications": [
                "Suspected meniscal tear (ICD-10: M23.2xx, M23.3xx)",
                "Suspected ligamentous injury (ICD-10: S83.5xx, S83.6xx)",
                "Knee pain with mechanical symptoms (ICD-10: M25.56x)",
                "Osteoarthritis requiring pre-surgical evaluation (ICD-10: M17.xx)",
                "Suspected osteochondral lesion (ICD-10: M93.2xx)"
            ],
            "prerequisites": [
                "Member must have a documented diagnosis consistent with one of the above conditions.",
                "Weight-bearing X-rays of the affected knee must be completed within the past 60 days prior to MRI request."
            ],
            "exclusion_criteria": [],
            "documentation_requirements": [
                "Recent clinical notes (within 30 days) documenting: History and physical examination",
                "Specific clinical findings (exam maneuvers, ROM, effusion)",
                "Duration and character of symptoms",
                "Conservative treatment records: Physical therapy notes with dates and number of sessions",
                "Medication trial documentation",
                "X-ray report (within 60 days)"
            ],
            "quantity_limits": {
                "description": "Not applicable"
            }
        },
        "source_references": [
            "RAD-KNEE-2024-SUPP",
            "CPT-4"
        ]
    },
    "context": ["n/a"],
    "raw_output": "n/a"
}


def test_automatic_rules():
    """Test with automatically extracted rules from policy"""
    print("=" * 80)
    print("TEST 1: AUTOMATIC RULE EXTRACTION FROM YOUR POLICY")
    print("=" * 80)
    
    # Normalize
    patient_norm = normalize_patient_evidence(patient_chart)
    
    print("\n📋 Normalized Patient Data:")
    print("-" * 80)
    for key, value in patient_norm.items():
        if key != "evidence_notes":  # Skip long notes for readability
            print(f"  {key}: {value}")
    
    # Auto-extract rules from policy
    policy_rules = normalize_policy_criteria(policy_insurance)
    
    print(f"\n📜 Extracted {len(policy_rules)} Rules from Policy:")
    print("-" * 80)
    for rule in policy_rules:
        print(f"\n  [{rule['id']}] {rule['description']}")
        for cond in rule['conditions']:
            print(f"    → {cond['field']} {cond['operator']} {cond['value']}")
    
    # Evaluate
    results = evaluate_all(patient_norm, policy_rules)
    
    print("\n" + "=" * 80)
    print("🏥 PRIOR AUTHORIZATION EVALUATION RESULTS")
    print("=" * 80)
    print(f"\n{'✅ APPROVED' if results['all_criteria_met'] else '❌ DENIED'}")
    print(f"\nRules Met: {results['rules_met']}/{results['total_rules']}")
    
    print("\n" + "-" * 80)
    print("Detailed Results:")
    print("-" * 80)
    
    for result in results['results']:
        status = "✅" if result['met'] else "❌"
        print(f"\n{status} [{result['rule_id']}] {result['description']}")
        
        if 'condition_details' in result:
            for detail in result['condition_details']:
                check_status = "  ✓" if detail['met'] else "  ✗"
                print(f"{check_status} {detail['condition']}")
                print(f"     Patient value: {detail['patient_value']}")


def test_manual_rules():
    """Test with manually specified rules"""
    print("\n\n" + "=" * 80)
    print("TEST 2: MANUAL RULE SPECIFICATION")
    print("=" * 80)
    
    # Normalize patient
    patient_norm = normalize_patient_evidence(patient_chart)
    
    # Define custom rules that match Aetna's actual requirements
    custom_rules = [
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
    
    print(f"\n📜 Manual Rules ({len(custom_rules)} total):")
    print("-" * 80)
    for rule in custom_rules:
        print(f"  [{rule['id']}] {rule['description']}")
    
    # Evaluate
    results = evaluate_all(patient_norm, custom_rules)
    
    print("\n" + "=" * 80)
    print("🏥 EVALUATION RESULTS")
    print("=" * 80)
    print(f"\n{'✅ APPROVED' if results['all_criteria_met'] else '❌ DENIED'}")
    print(f"\nRules Met: {results['rules_met']}/{results['total_rules']}")
    
    print("\n" + "-" * 80)
    print("Detailed Results:")
    print("-" * 80)
    
    for result in results['results']:
        status = "✅" if result['met'] else "❌"
        print(f"\n{status} [{result['rule_id']}] {result['description']}")
        
        if 'condition_details' in result:
            for detail in result['condition_details']:
                check_status = "  ✓" if detail['met'] else "  ✗"
                print(f"{check_status} {detail['condition']}")
                print(f"     Patient value: {detail['patient_value']}")


def test_failing_case():
    """Test with a patient that should fail"""
    print("\n\n" + "=" * 80)
    print("TEST 3: FAILING CASE (Insufficient PT)")
    print("=" * 80)
    
    # Modify patient to have insufficient PT
    failing_patient = json.loads(json.dumps(patient_chart))  # Deep copy
    failing_patient["analysis"]["requirements"]["conservative_therapy"]["physical_therapy"]["duration_weeks"] = 4
    
    patient_norm = normalize_patient_evidence(failing_patient)
    
    custom_rules = [
        {
            "id": "pt_minimum",
            "description": "PT must be at least 6 weeks",
            "logic": "all",
            "conditions": [
                {"field": "pt_duration_weeks", "operator": "gte", "value": 6}
            ]
        }
    ]
    
    results = evaluate_all(patient_norm, custom_rules)
    
    print(f"\nPatient PT Duration: {patient_norm['pt_duration_weeks']} weeks")
    print(f"Required: 6+ weeks")
    print(f"\nResult: {'✅ APPROVED' if results['all_criteria_met'] else '❌ DENIED'}")
    
    for result in results['results']:
        status = "✅" if result['met'] else "❌"
        print(f"\n{status} {result['description']}")
        if 'condition_details' in result:
            for detail in result['condition_details']:
                print(f"  → {detail['condition']}: Patient has {detail['patient_value']}")


if __name__ == "__main__":
    test_automatic_rules()
    test_manual_rules()
    test_failing_case()