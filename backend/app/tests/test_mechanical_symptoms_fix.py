#!/usr/bin/env python3
"""
Test to verify Issue #52 fix: mechanical symptoms normalization bug

Bug: "mechanical symptoms" was not being added to the approved indication list
in normalize_policy_criteria(), causing patients with mechanical symptoms to
incorrectly fail clinical_indication_requirement.

This test verifies that when a policy contains "Mechanical symptoms" in the
clinical_indications list, it gets correctly normalized and patients with
mechanical symptoms pass the evaluation.
"""

import json
import sys
sys.path.insert(0, '/home/runner/work/pauth_rc/pauth_rc/backend')

from app.normalization.normalized_custom import normalize_patient_evidence, normalize_policy_criteria
from app.rules.rule_engine import evaluate_all

def test_mechanical_symptoms_normalization():
    """
    Test that policy with "Mechanical symptoms" in clinical_indications
    correctly normalizes to include "mechanical symptoms" in approved list.
    """
    print("=" * 80)
    print("ISSUE #52 TEST: Mechanical Symptoms Normalization")
    print("=" * 80)

    # Policy with "Mechanical symptoms" in clinical_indications
    # This mimics what RAG pipeline extracts from Utah Medicaid or Aetna policies
    policy = {
        "payer": "Utah Medicaid",
        "cpt_code": "73721",
        "coverage_criteria": {
            "clinical_indications": [
                "Suspected meniscal tear",
                "Mechanical symptoms or instability",  # This should normalize to "mechanical symptoms"
                "Suspected ligamentous injury",
                "Positive McMurray's test"
            ],
            "prerequisites": [
                "At least 6 weeks of conservative therapy",
                "X-rays within 60 days"
            ],
            "documentation_requirements": [
                "Recent clinical notes (within 30 days)"
            ]
        }
    }

    print("\n1. Normalizing policy criteria...")
    normalized_policy = normalize_policy_criteria(policy)

    # Find the clinical_indication_requirement rule
    clinical_indication_rule = None
    for rule in normalized_policy:
        if rule['id'] == 'clinical_indication_requirement':
            clinical_indication_rule = rule
            break

    if not clinical_indication_rule:
        print("❌ FAIL: clinical_indication_requirement rule not found!")
        return False

    approved_indications = clinical_indication_rule['conditions'][0]['value']
    print(f"\n   Approved clinical indications: {approved_indications}")

    # Verify "mechanical symptoms" is in the list
    if "mechanical symptoms" not in approved_indications:
        print(f"\n❌ FAIL: 'mechanical symptoms' NOT in approved list!")
        print(f"   This is the bug described in Issue #52")
        return False

    print(f"\n✓ SUCCESS: 'mechanical symptoms' is in approved list")

    # Now test with a patient who has mechanical symptoms
    print("\n2. Testing patient with mechanical symptoms...")

    patient = {
        "symptom_duration_months": 5,
        "conservative_therapy": {
            "physical_therapy": {"attempted": True, "duration_weeks": 8},
            "nsaids": {"documented": True, "outcome": "failed"}
        },
        "imaging": {
            "documented": True,
            "type": "X-ray",
            "months_ago": 1
        },
        "pain_characteristics": {
            "quality": "Sharp pain with mechanical catching and locking"  # Should extract "mechanical symptoms"
        },
        "evidence_notes": [
            "Left knee pain for 5 months",
            "Patient reports mechanical catching and locking",
            "Limited range of motion"
        ],
        "_metadata": {
            "validation_passed": True,
            "hallucinations_detected": 0,
            "clinical_notes_days_ago": 15
        }
    }

    normalized_patient = normalize_patient_evidence(patient)
    print(f"   Extracted clinical indication: '{normalized_patient.get('clinical_indication')}'")

    if normalized_patient.get('clinical_indication') != "mechanical symptoms":
        print(f"\n⚠️  WARNING: Patient extraction didn't get 'mechanical symptoms'")
        print(f"   Got: '{normalized_patient.get('clinical_indication')}'")
        print(f"   This is a separate issue from #52")

    # Evaluate patient against policy
    print("\n3. Evaluating patient against policy...")
    result = evaluate_all(normalized_patient, normalized_policy)

    # Find clinical_indication result
    clinical_indication_result = None
    for rule_result in result['results']:
        if rule_result['rule_id'] == 'clinical_indication_requirement':
            clinical_indication_result = rule_result
            break

    if not clinical_indication_result:
        print("❌ FAIL: clinical_indication_requirement result not found!")
        return False

    print(f"\n   Clinical indication rule status: {'PASS' if clinical_indication_result['met'] else 'FAIL'}")

    for detail in clinical_indication_result['condition_details']:
        print(f"   Condition: {detail['condition']}")
        print(f"   Patient value: {detail['patient_value']}")
        print(f"   Required values: {detail.get('expected_value', 'N/A')}")
        print(f"   Met: {detail['met']}")

    # Final verdict
    if normalized_patient.get('clinical_indication') == "mechanical symptoms":
        if clinical_indication_result['met']:
            print(f"\n✅ TEST PASSED: Patient with 'mechanical symptoms' correctly passes evaluation")
            return True
        else:
            print(f"\n❌ TEST FAILED: Patient with 'mechanical symptoms' should pass but failed!")
            print(f"   This indicates Issue #52 is NOT fixed")
            return False
    else:
        print(f"\n⚠️  TEST INCONCLUSIVE: Patient didn't extract mechanical symptoms")
        print(f"   But policy normalization appears correct")
        return "inconclusive"


def test_policy_with_multiple_mechanical_variants():
    """
    Test that various phrasings of mechanical symptoms all normalize correctly.
    """
    print("\n" + "=" * 80)
    print("BONUS TEST: Multiple Mechanical Symptoms Phrasings")
    print("=" * 80)

    test_cases = [
        "Mechanical symptoms",
        "mechanical symptoms or instability",
        "Knee pain with mechanical symptoms",
        "mechanical symptoms — locking, catching",
        "Mechanical instability"
    ]

    all_passed = True

    for i, indication_text in enumerate(test_cases, 1):
        policy = {
            "coverage_criteria": {
                "clinical_indications": [indication_text],
                "prerequisites": [],
                "documentation_requirements": []
            }
        }

        normalized_policy = normalize_policy_criteria(policy)

        # Find clinical indication rule
        approved = None
        for rule in normalized_policy:
            if rule['id'] == 'clinical_indication_requirement':
                approved = rule['conditions'][0]['value']
                break

        if approved and "mechanical symptoms" in approved:
            print(f"{i}. ✓ '{indication_text}' → includes 'mechanical symptoms'")
        else:
            print(f"{i}. ✗ '{indication_text}' → MISSING 'mechanical symptoms'")
            print(f"      Got: {approved}")
            all_passed = False

    return all_passed


if __name__ == "__main__":
    print("\nRunning Issue #52 Fix Verification Tests\n")

    test1_result = test_mechanical_symptoms_normalization()
    test2_result = test_policy_with_multiple_mechanical_variants()

    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    if test1_result == True and test2_result == True:
        print("✅ ALL TESTS PASSED - Issue #52 is FIXED")
        sys.exit(0)
    elif test1_result == "inconclusive":
        print("⚠️  TESTS INCONCLUSIVE - Policy normalization appears correct")
        print("   But patient extraction needs investigation")
        sys.exit(1)
    else:
        print("❌ TESTS FAILED - Issue #52 is NOT fixed")
        sys.exit(1)
