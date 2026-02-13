#!/usr/bin/env python3
"""
Quick test to verify clinical indication implementation
"""

import json
import sys
sys.path.insert(0, '/home/runner/work/pauth_rc/pauth_rc/backend')

from app.normalization.normalized_custom import normalize_patient_evidence, normalize_policy_criteria
from app.rules.rule_engine import evaluate_all

# Test case 1: Patient with meniscal tear (should pass)
patient_with_indication = {
    "symptom_duration_months": 4,
    "conservative_therapy": {
        "physical_therapy": {"attempted": True, "duration_weeks": 8},
        "nsaids": {"documented": True, "outcome": "failed"}
    },
    "imaging": {
        "documented": True,
        "type": "X-ray",
        "months_ago": 1
    },
    "functional_impairment": {"documented": True},
    "evidence_notes": [
        "Right knee pain for 4 months",
        "Suspected medial meniscal tear",
        "McMurray's test positive",
        "mechanical catching sensation"
    ],
    "_metadata": {
        "validation_passed": True,
        "hallucinations_detected": 0
    }
}

# Test case 2: Patient without valid indication (should fail)
patient_without_indication = {
    "symptom_duration_months": 4,
    "conservative_therapy": {
        "physical_therapy": {"attempted": True, "duration_weeks": 8},
        "nsaids": {"documented": True, "outcome": "failed"}
    },
    "imaging": {
        "documented": True,
        "type": "X-ray",
        "months_ago": 1
    },
    "functional_impairment": {"documented": True},
    "evidence_notes": [
        "Right knee pain for 4 months",
        "No specific findings"
    ],
    "_metadata": {
        "validation_passed": True,
        "hallucinations_detected": 0
    }
}

# Policy with clinical indications
policy = {
    "payer": "Aetna",
    "cpt_code": "73721",
    "coverage_criteria": {
        "clinical_indications": [
            "Meniscal tear",
            "Mechanical symptoms or instability",
            "Suspected complete ligament rupture (ACL, PCL, MCL, LCL)"
        ],
        "prerequisites": [
            "At least 6 weeks of conservative therapy",
            "X-rays within 60 days"
        ],
        "documentation_requirements": []
    }
}

print("=" * 80)
print("TEST 1: Patient WITH valid clinical indication (meniscal tear)")
print("=" * 80)

normalized_patient_1 = normalize_patient_evidence(patient_with_indication)
print(f"\nExtracted clinical indication: {normalized_patient_1.get('clinical_indication')}")

normalized_policy = normalize_policy_criteria(policy)
print(f"\nGenerated {len(normalized_policy)} policy rules:")
for rule in normalized_policy:
    if rule['id'] == 'clinical_indication_requirement':
        print(f"  - {rule['id']}: {rule['description']}")
        print(f"    Allowed indications: {rule['conditions'][0]['value']}")

result_1 = evaluate_all(normalized_patient_1, normalized_policy)
print(f"\nEvaluation result: {'PASS' if result_1['all_criteria_met'] else 'FAIL'}")
print(f"Rules met: {result_1['rules_met']}/{result_1['total_rules']}")

# Show clinical indication rule details
for rule_result in result_1['results']:
    if rule_result['rule_id'] == 'clinical_indication_requirement':
        print(f"\nClinical indication rule details:")
        print(f"  Status: {'PASS' if rule_result['met'] else 'FAIL'}")
        for detail in rule_result['condition_details']:
            print(f"  {detail['condition']}")
            print(f"    Patient value: {detail['patient_value']}")
            print(f"    Met: {detail['met']}")

print("\n" + "=" * 80)
print("TEST 2: Patient WITHOUT valid clinical indication")
print("=" * 80)

normalized_patient_2 = normalize_patient_evidence(patient_without_indication)
print(f"\nExtracted clinical indication: {normalized_patient_2.get('clinical_indication')}")

result_2 = evaluate_all(normalized_patient_2, normalized_policy)
print(f"\nEvaluation result: {'PASS' if result_2['all_criteria_met'] else 'FAIL'}")
print(f"Rules met: {result_2['rules_met']}/{result_2['total_rules']}")

# Show clinical indication rule details
for rule_result in result_2['results']:
    if rule_result['rule_id'] == 'clinical_indication_requirement':
        print(f"\nClinical indication rule details:")
        print(f"  Status: {'PASS' if rule_result['met'] else 'FAIL'}")
        for detail in rule_result['condition_details']:
            print(f"  {detail['condition']}")
            print(f"    Patient value: {detail['patient_value']}")
            print(f"    Met: {detail['met']}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Test 1 (with indication): {'✓ PASSED' if result_1['all_criteria_met'] else '✗ FAILED (expected to pass)'}")
print(f"Test 2 (without indication): {'✓ PASSED' if not result_2['all_criteria_met'] else '✗ FAILED (expected to fail)'}")
