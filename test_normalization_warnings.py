#!/usr/bin/env python3
"""
Test script to verify that normalize_policy_criteria() logs warnings
for unmapped policy criteria.
"""

import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.normalization.normalized_custom import normalize_policy_criteria

# Configure logging to see warnings
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

def test_renal_function_warning():
    """Test that renal function criteria trigger warnings"""
    print("\n" + "="*80)
    print("TEST 1: Policy with renal function requirement")
    print("="*80)

    policy_with_renal = {
        "rules": {
            "payer": "Utah Medicaid",
            "cpt_code": "73722",
            "coverage_criteria": {
                "prerequisites": [
                    "X-rays within 60 days",
                    "Physical therapy for at least 6 weeks"
                ],
                "documentation_requirements": [
                    "Creatinine/eGFR within 6 months if member has renal disease",
                    "Conservative treatment records"
                ]
            }
        },
        "context": []
    }

    rules = normalize_policy_criteria(policy_with_renal)
    print(f"\nGenerated {len(rules)} rules")
    print("Expected: WARNING about skipped renal function criterion")

def test_conservative_completion_warning():
    """Test that conservative treatment completion triggers warnings"""
    print("\n" + "="*80)
    print("TEST 2: Policy with conservative treatment completion requirement")
    print("="*80)

    policy_with_completion = {
        "rules": {
            "payer": "Utah Medicaid",
            "cpt_code": "73721",
            "coverage_criteria": {
                "prerequisites": [
                    "Conservative treatment completed",
                    "X-rays within 60 days"
                ],
                "documentation_requirements": [
                    "Physical therapy notes",
                    "Medication trial documentation"
                ]
            }
        },
        "context": []
    }

    rules = normalize_policy_criteria(policy_with_completion)
    print(f"\nGenerated {len(rules)} rules")
    print("Expected: WARNING about conservative treatment completion")

def test_multiple_unmapped_criteria():
    """Test policy with multiple unmapped criteria"""
    print("\n" + "="*80)
    print("TEST 3: Policy with multiple unmapped criteria")
    print("="*80)

    policy_complex = {
        "rules": {
            "payer": "Utah Medicaid",
            "cpt_code": "73722",
            "coverage_criteria": {
                "prerequisites": [
                    "Conservative treatment completed",
                    "X-rays within 60 days"
                ],
                "documentation_requirements": [
                    "Renal function documentation (creatinine/eGFR)",
                    "Contrast allergy documentation if applicable",
                    "Documentation of any contraindications"
                ]
            }
        },
        "context": []
    }

    rules = normalize_policy_criteria(policy_complex)
    print(f"\nGenerated {len(rules)} rules")
    print("Expected: WARNINGS about renal function, conservative completion, allergy, contraindications")

def test_normal_policy_no_warnings():
    """Test that a normal Aetna policy doesn't trigger false warnings"""
    print("\n" + "="*80)
    print("TEST 4: Normal Aetna policy (should not trigger warnings)")
    print("="*80)

    normal_policy = {
        "rules": {
            "payer": "Aetna",
            "cpt_code": "73721",
            "coverage_criteria": {
                "prerequisites": [
                    "At least 6 weeks of conservative therapy including physical therapy and NSAIDs",
                    "X-rays within 60 days"
                ],
                "documentation_requirements": [
                    "Recent clinical notes (within 30 days)",
                    "Physical therapy notes",
                    "Medication trial documentation"
                ]
            }
        },
        "context": []
    }

    rules = normalize_policy_criteria(normal_policy)
    print(f"\nGenerated {len(rules)} rules")
    print("Expected: No warnings about skipped criteria")

if __name__ == "__main__":
    print("\nTesting normalize_policy_criteria() warning system")
    print("This verifies that unmapped criteria are logged, not silently dropped\n")

    test_renal_function_warning()
    test_conservative_completion_warning()
    test_multiple_unmapped_criteria()
    test_normal_policy_no_warnings()

    print("\n" + "="*80)
    print("TESTS COMPLETE")
    print("="*80)
    print("\nReview the warnings above to verify that unmapped criteria are being detected.")
