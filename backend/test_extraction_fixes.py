"""
Test script to verify Fix #1: Data Extraction Nulls

This tests the _validate_extraction_completeness() function
to ensure it correctly identifies and auto-fixes null values.

Priority: P0 - CRITICAL
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from services.evidence import EvidenceExtractor
import json


def test_imaging_months_ago_fix():
    """Test that imaging_months_ago gets auto-fixed when null"""
    print("\n" + "="*70)
    print("TEST 1: Imaging months_ago null fix")
    print("="*70)

    # Sample chart that mentions imaging
    chart_text = """
    Patient Name: Brittany Okafor
    Date of Visit: 2025-01-30

    Chief Complaint: Right knee pain x 2 weeks

    History: Patient reports acute onset right knee pain following a fall.
    Pain is 5/10 at rest, 7/10 with activity. Mild effusion noted at today's visit.

    Prior Imaging: X-ray Right Knee dated 01/30/2025 shows: Normal. No fracture,
    no significant arthritis.

    Physical Exam:
    - Mild effusion present
    - Full ROM with pain at end range
    - No obvious deformity

    Assessment: Acute knee pain, suspected internal derangement vs contusion
    Red flags: Concern for occult fracture or ligamentous injury given mechanism

    Plan:
    - NSAIDs prescribed
    - Ice, rest, elevation
    - MRI if no improvement in 2 weeks
    """

    # Create extractor instance (without Groq for this test)
    extractor = EvidenceExtractor(use_groq=False)

    # Simulate extracted data with null imaging_months_ago
    # This simulates what happens when the LLM extraction fails
    extracted_data = {
        "patient_name": "Brittany Okafor",
        "clinical_notes_date": "2025-01-30",
        "imaging": {
            "documented": True,
            "type": "X-ray",
            "body_part": "Right Knee",
            "laterality": "right",
            "months_ago": None,  # NULL - should be auto-fixed
            "findings": "Normal. No fracture, no significant arthritis."
        },
        "red_flags": {
            "documented": True,
            "description": "Concern for occult fracture or ligamentous injury"
        },
        "clinical_indication": None,  # NULL - should be auto-fixed to "red flag"
        "evidence_notes": ["Right knee pain x 2 weeks"]
    }

    print("\nBEFORE validation:")
    print(f"  imaging_months_ago: {extracted_data['imaging']['months_ago']}")
    print(f"  clinical_indication: {extracted_data['clinical_indication']}")

    # Apply completeness validation
    fixed_data = extractor._validate_extraction_completeness(extracted_data, chart_text)

    print("\nAFTER validation:")
    print(f"  imaging_months_ago: {fixed_data['imaging']['months_ago']}")
    print(f"  clinical_indication: {fixed_data['clinical_indication']}")

    print("\nMetadata:")
    print(f"  Issues found: {fixed_data['_metadata']['completeness_issues']}")
    print(f"  Fixes applied: {fixed_data['_metadata']['completeness_fixes']}")
    print(f"  Check passed: {fixed_data['_metadata']['completeness_check_passed']}")

    # Verify fixes were applied
    assert fixed_data['imaging']['months_ago'] is not None, "imaging_months_ago should be fixed"
    assert fixed_data['clinical_indication'] == "red flag", "clinical_indication should be 'red flag'"

    print("\n✅ TEST PASSED: Null values were successfully auto-fixed!")


def test_pt_duration_extraction():
    """Test that PT duration_weeks gets extracted from chart text"""
    print("\n" + "="*70)
    print("TEST 2: PT duration_weeks extraction")
    print("="*70)

    chart_text = """
    Patient: Denise Kowalczyk
    Date: 2025-01-27

    Chief Complaint: Left knee pain x 6 months

    History: Patient has been experiencing progressive left knee pain for the past
    6 months. She has completed 8 weeks of physical therapy with modest improvement
    early on, but symptoms plateaued at week 6 and she experienced recurrence of
    effusion at week 8. She also tried NSAIDs with partial relief.

    Exam: Moderate effusion, limited ROM

    Plan: Consider MRI to evaluate for internal derangement
    """

    extractor = EvidenceExtractor(use_groq=False)

    extracted_data = {
        "conservative_therapy": {
            "physical_therapy": {
                "attempted": True,
                "duration_weeks": None,  # NULL - should be extracted as 8
                "outcome": "partial"
            }
        }
    }

    print("\nBEFORE validation:")
    print(f"  PT duration_weeks: {extracted_data['conservative_therapy']['physical_therapy']['duration_weeks']}")

    fixed_data = extractor._validate_extraction_completeness(extracted_data, chart_text)

    print("\nAFTER validation:")
    print(f"  PT duration_weeks: {fixed_data['conservative_therapy']['physical_therapy']['duration_weeks']}")

    print("\nMetadata:")
    print(f"  Issues found: {fixed_data['_metadata']['completeness_issues']}")
    print(f"  Fixes applied: {fixed_data['_metadata']['completeness_fixes']}")

    # Verify fix
    assert fixed_data['conservative_therapy']['physical_therapy']['duration_weeks'] == 8, "PT duration should be 8 weeks"

    print("\n✅ TEST PASSED: PT duration was successfully extracted!")


def test_no_false_positives():
    """Test that validation doesn't flag issues when data is complete"""
    print("\n" + "="*70)
    print("TEST 3: No false positives for complete data")
    print("="*70)

    chart_text = "Complete patient chart..."

    extractor = EvidenceExtractor(use_groq=False)

    # Properly extracted data - should pass without issues
    extracted_data = {
        "imaging": {
            "documented": True,
            "months_ago": 2  # Already populated
        },
        "red_flags": {
            "documented": False  # Not documented
        },
        "clinical_indication": "meniscal tear",  # Already set
        "conservative_therapy": {
            "physical_therapy": {
                "attempted": True,
                "duration_weeks": 8  # Already populated
            }
        }
    }

    print("\nValidating complete data...")
    fixed_data = extractor._validate_extraction_completeness(extracted_data, chart_text)

    print(f"\nCheck passed: {fixed_data['_metadata']['completeness_check_passed']}")
    print(f"Issues found: {len(fixed_data['_metadata']['completeness_issues'])}")
    print(f"Fixes applied: {len(fixed_data['_metadata']['completeness_fixes'])}")

    assert fixed_data['_metadata']['completeness_check_passed'] == True, "Should pass when data is complete"
    assert len(fixed_data['_metadata']['completeness_issues']) == 0, "Should have no issues"

    print("\n✅ TEST PASSED: No false positives detected!")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("TESTING FIX #1: DATA EXTRACTION NULLS")
    print("Priority: P0 - CRITICAL")
    print("="*70)

    try:
        test_imaging_months_ago_fix()
        test_pt_duration_extraction()
        test_no_false_positives()

        print("\n" + "="*70)
        print("ALL TESTS PASSED! ✅")
        print("="*70)
        print("\nThe Data Extraction Nulls fix is working correctly.")
        print("\nKey improvements:")
        print("  1. Auto-fixes null imaging_months_ago values")
        print("  2. Auto-sets clinical_indication to 'red flag' when red flags are documented")
        print("  3. Extracts PT duration from chart text when null")
        print("  4. Logs all issues and fixes in metadata")
        print("  5. No false positives for complete data")
        print("\nNext steps:")
        print("  - Test with real patient data")
        print("  - Monitor logs for completeness issues in production")
        print("  - Proceed to Fix #2: Clinical Indication Mapping")
        print("="*70 + "\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
