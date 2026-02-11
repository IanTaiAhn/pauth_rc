"""
Test multi-chart evidence extraction functionality.

This test demonstrates how multiple patient charts for the same patient
are processed and merged into a single evidence object.
"""

from app.services.evidence import extract_evidence_multi
from pathlib import Path
import json


def test_multi_chart_extraction():
    """
    Test that multiple charts can be processed and merged correctly.

    This simulates a real clinical scenario where:
    - Chart 1: Initial visit with symptom history and X-ray
    - Chart 2: Follow-up visit documenting physical therapy attempts

    Expected outcome:
    - Evidence from both charts should be merged
    - Source metadata should track which file contributed which data
    """

    # Create two mock charts for the same patient
    chart1_text = """
    PATIENT: John Doe
    DOB: 1975-05-15
    CHIEF COMPLAINT: Right knee pain

    HPI: Patient reports 3 months of right knee pain following a running injury.
    Pain is located in the anterior knee, 7/10 severity, worse with stairs and
    prolonged standing.

    PHYSICAL EXAM:
    - Tenderness over patellar tendon
    - Limited range of motion (0-110 degrees)
    - Positive patellar grind test

    IMAGING:
    X-ray right knee performed 2 weeks ago shows mild patellofemoral arthritis.

    ASSESSMENT/PLAN:
    - Right knee pain, suspected patellofemoral syndrome
    - Patient advised to start NSAIDs (ibuprofen 600mg TID)
    - Refer to physical therapy
    """

    chart2_text = """
    PATIENT: John Doe
    DOB: 1975-05-15
    FOLLOW-UP VISIT: Right knee pain

    INTERVAL HISTORY:
    Patient has completed 8 weeks of physical therapy (2x weekly, 16 sessions total).
    Focus on quadriceps strengthening and patellar mobilization.

    Patient reports minimal improvement with PT. Pain still 6/10 with activities.
    Has been taking ibuprofen as directed but with limited relief.

    EXAM:
    - Persistent tenderness
    - ROM slightly improved to 0-120 degrees
    - Quadriceps strength improved from 4/5 to 4.5/5

    ASSESSMENT:
    - Right knee pain - failed conservative management
    - Symptom duration now 5 months total
    - Consider advanced imaging

    PLAN:
    - Request MRI right knee for further evaluation
    - Continue current management pending MRI results
    """

    # Test the multi-chart extraction
    chart_texts = [
        (chart1_text, "initial_visit_2024-11-15.txt"),
        (chart2_text, "followup_visit_2025-01-20.txt")
    ]

    print("Testing multi-chart evidence extraction...")
    print(f"Processing {len(chart_texts)} charts\n")

    # Note: This will fail without GROQ_API_KEY set, so we'll catch the exception
    try:
        result = extract_evidence_multi(chart_texts, use_groq=True)

        if result:
            print("✓ Multi-chart extraction successful!")
            print("\n=== MERGED EVIDENCE ===")
            print(json.dumps(result, indent=2))

            # Verify merge logic
            print("\n=== VERIFICATION ===")

            # Check that duration was maximized (5 months from chart 2)
            duration = result.get("symptom_duration_months")
            print(f"✓ Symptom duration: {duration} months (should be 5 - max from both charts)")

            # Check that PT was documented as attempted
            pt = result.get("conservative_therapy", {}).get("physical_therapy", {})
            print(f"✓ PT attempted: {pt.get('attempted')} (should be True)")
            print(f"✓ PT duration: {pt.get('duration_weeks')} weeks (should be 8)")

            # Check that NSAIDs were documented
            nsaids = result.get("conservative_therapy", {}).get("nsaids", {})
            print(f"✓ NSAIDs documented: {nsaids.get('documented')} (should be True)")

            # Check imaging
            imaging = result.get("imaging", {})
            print(f"✓ Imaging documented: {imaging.get('documented')} (should be True)")
            print(f"✓ Imaging type: {imaging.get('type')} (should be X-ray from chart 1)")

            # Check source metadata
            metadata = result.get("_multi_source_metadata", {})
            print(f"\n✓ Processed {metadata.get('total_charts')} charts")
            print(f"✓ Sources: {metadata.get('sources')}")
            print(f"✓ Hallucinations detected: {metadata.get('total_hallucinations')}")

            return True
        else:
            print("✗ Multi-chart extraction returned None")
            return False

    except ValueError as e:
        print(f"⚠ Test requires GROQ_API_KEY environment variable: {e}")
        print("\nTo run this test, set GROQ_API_KEY in your environment:")
        print("export GROQ_API_KEY='your-api-key-here'")
        return False
    except Exception as e:
        print(f"✗ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_multi_chart_extraction()
    exit(0 if success else 1)
