"""
Tests for structural and semantic validation.
"""

from app.validation import validate


def test_valid_template_passes():
    template = {
        "payer": "medicare",
        "lcd_code": "L36007",
        "checklist_sections": [
            {
                "id": "eligible_diagnosis",
                "title": "Eligible Diagnosis",
                "description": "Patient must have one of these diagnoses.",
                "requirement_type": "any",
                "items": [
                    {"field": "meniscal_tear", "label": "Meniscal Tear", "input_type": "checkbox"}
                ],
            }
        ],
        "exception_pathways": [],
        "exclusions": [],
        "denial_prevention_tips": [],
        "submission_reminders": [],
    }
    errors = validate(template)
    assert errors == []


def test_missing_required_field():
    template = {
        "payer": "medicare",
        # lcd_code missing
        "checklist_sections": [],
    }
    errors = validate(template)
    assert any("lcd_code" in e for e in errors)


def test_count_gte_without_threshold():
    template = {
        "payer": "medicare",
        "lcd_code": "L36007",
        "checklist_sections": [
            {
                "id": "conservative_treatment",
                "title": "Conservative Treatment",
                "description": "Patient must complete at least 2 of the following.",
                "requirement_type": "count_gte",
                # threshold missing
                "items": [
                    {"field": "pt", "label": "Physical Therapy", "input_type": "checkbox"},
                    {"field": "nsaids", "label": "NSAIDs", "input_type": "checkbox"},
                ],
            }
        ],
        "exception_pathways": [],
        "exclusions": [],
        "denial_prevention_tips": [],
        "submission_reminders": [],
    }
    errors = validate(template)
    assert any("threshold" in e for e in errors)


def test_semantic_count_gte_mismatch():
    template = {
        "payer": "medicare",
        "lcd_code": "L36007",
        "checklist_sections": [
            {
                "id": "conservative_treatment",
                "title": "Conservative Treatment",
                "description": "Patient must complete at least 2 of the following.",
                "requirement_type": "all",  # wrong — should be count_gte
                "items": [
                    {"field": "pt", "label": "Physical Therapy", "input_type": "checkbox"},
                    {"field": "nsaids", "label": "NSAIDs", "input_type": "checkbox"},
                ],
            }
        ],
        "exception_pathways": [],
        "exclusions": [],
        "denial_prevention_tips": [],
        "submission_reminders": [],
    }
    errors = validate(template)
    assert any("count_gte" in e for e in errors)
