"""
Custom normalization functions for your specific JSON formats
"""

from typing import Any, Dict, List


def normalize_patient_evidence(evidence: dict) -> dict:
    """
    Normalize YOUR specific patient chart JSON format.

    Input format (from Groq):
    {
      "filename": "...",
      "score": 100,
      "requirements": {
        "symptom_duration_months": 4,
        "conservative_therapy": {...},
        "imaging": {...},
        ...
      },
      "missing_items": [...]
    }

    Handles edge cases and ensures all fields have proper defaults.
    """
    normalized = {}

    # Extract the requirements section (directly at top level in Groq output)
    requirements = evidence.get("requirements", {})

    # Symptom duration - handle both months and weeks
    symptom_months = requirements.get("symptom_duration_months")
    symptom_weeks = requirements.get("symptom_duration_weeks")

    if symptom_months is not None:
        normalized["symptom_duration_months"] = symptom_months
        normalized["symptom_duration_weeks"] = symptom_months * 4  # Convert to weeks
    elif symptom_weeks is not None:
        normalized["symptom_duration_weeks"] = symptom_weeks
        normalized["symptom_duration_months"] = symptom_weeks / 4  # Convert to months
    else:
        normalized["symptom_duration_months"] = None
        normalized["symptom_duration_weeks"] = None

    # Conservative therapy
    conservative = requirements.get("conservative_therapy", {})

    # Physical therapy - handle multiple possible field names
    pt = conservative.get("physical_therapy", {})
    normalized["pt_attempted"] = pt.get("attempted", False)

    # Duration can be in different fields
    pt_duration = pt.get("duration_weeks") or pt.get("weeks") or pt.get("duration")
    normalized["pt_duration_weeks"] = pt_duration

    # Sessions count
    normalized["pt_sessions"] = pt.get("sessions") or pt.get("session_count")

    # NSAIDs - handle various outcome formats
    nsaids = conservative.get("nsaids", {})
    normalized["nsaid_documented"] = nsaids.get("documented", False)
    normalized["nsaid_outcome"] = nsaids.get("outcome")

    # Check for failed/unsuccessful outcome (multiple possible values)
    outcome = nsaids.get("outcome") or ""
    outcome = outcome.lower() if isinstance(outcome, str) else ""
    normalized["nsaid_failed"] = outcome in ["failed", "no relief", "unsuccessful", "ineffective"]

    # Injections
    injections = conservative.get("injections", {})
    normalized["injection_documented"] = injections.get("documented", False)
    normalized["injection_outcome"] = injections.get("outcome")

    outcome = injections.get("outcome") or ""
    outcome = outcome.lower() if isinstance(outcome, str) else ""
    normalized["injection_failed"] = outcome in ["failed", "no relief", "unsuccessful", "ineffective"]

    # Imaging - normalize type field
    imaging = requirements.get("imaging", {})
    normalized["imaging_documented"] = imaging.get("documented", False)

    # Normalize imaging type (handle case variations)
    imaging_type = imaging.get("type")
    if imaging_type:
        imaging_type_lower = imaging_type.lower()
        if "x-ray" in imaging_type_lower or "xray" in imaging_type_lower:
            normalized["imaging_type"] = "X-ray"
        elif "mri" in imaging_type_lower:
            normalized["imaging_type"] = "MRI"
        elif "ct" in imaging_type_lower:
            normalized["imaging_type"] = "CT"
        else:
            normalized["imaging_type"] = imaging_type
    else:
        normalized["imaging_type"] = None

    normalized["imaging_body_part"] = imaging.get("body_part")
    normalized["imaging_months_ago"] = imaging.get("months_ago")

    # Convert days to months if needed
    imaging_days_ago = imaging.get("days_ago")
    if imaging_days_ago is not None and normalized["imaging_months_ago"] is None:
        normalized["imaging_months_ago"] = imaging_days_ago / 30

    # Functional impairment
    functional = requirements.get("functional_impairment", {})
    normalized["functional_impairment_documented"] = functional.get("documented", False)
    normalized["functional_impairment_description"] = functional.get("description")

    # Metadata - ensure defaults
    metadata = requirements.get("_metadata", {})
    normalized["validation_passed"] = metadata.get("validation_passed", False)
    normalized["hallucinations_detected"] = metadata.get("hallucinations_detected", 0)

    # Evidence notes
    normalized["evidence_notes"] = requirements.get("evidence_notes", [])

    # Top level data from Groq output
    normalized["score"] = evidence.get("score")
    normalized["missing_items"] = evidence.get("missing_items", [])
    normalized["filename"] = evidence.get("filename")

    # Add timestamp if present (may not be in Groq output)
    normalized["timestamp"] = evidence.get("timestamp")

    return normalized


def normalize_policy_criteria(criteria: dict) -> list:
    """
    Normalize YOUR specific insurance policy JSON format.

    Input format (from Groq):
    {
      "rules": {
        "payer": "Aetna",
        "cpt_code": "73721",
        "coverage_criteria": {
          "clinical_indications": [...],
          "prerequisites": [...],
          "documentation_requirements": [...]
        }
      },
      "context": [...],
      "raw_output": "..."
    }

    Output: List of rules in standardized condition format
    """
    rules_list = []

    rules = criteria.get("rules", {})
    coverage = rules.get("coverage_criteria", {})

    # Extract payer and CPT for reference
    payer = rules.get("payer")
    cpt_code = rules.get("cpt_code")

    # Extract context for more intelligent parsing
    context = criteria.get("context", [])
    context_text = " ".join(context) if isinstance(context, list) else ""

    # Rule 1: Prerequisites - X-ray/Imaging within timeframe
    prerequisites = coverage.get("prerequisites", [])
    prereq_text = " ".join(prerequisites).lower()

    # Check for imaging requirements with timeframe
    if "x-ray" in prereq_text or "imaging" in prereq_text:
        # Extract timeframe (60 days, 2 months, etc.)
        imaging_months = 2  # default
        if "60 days" in prereq_text or "60-day" in prereq_text:
            imaging_months = 2
        elif "90 days" in prereq_text or "3 months" in prereq_text:
            imaging_months = 3
        elif "30 days" in prereq_text or "1 month" in prereq_text:
            imaging_months = 1

        rules_list.append({
            "id": "imaging_requirement",
            "description": f"Imaging (X-ray) must be completed within {imaging_months} months",
            "logic": "all",
            "conditions": [
                {
                    "field": "imaging_documented",
                    "operator": "eq",
                    "value": True
                },
                {
                    "field": "imaging_months_ago",
                    "operator": "lte",
                    "value": imaging_months
                }
            ]
        })

    # Rule 2: Conservative therapy - Physical Therapy
    doc_requirements = coverage.get("documentation_requirements", [])
    doc_text = " ".join(doc_requirements).lower()

    # Check context for PT duration requirements (e.g., "6 weeks", "minimum 6 sessions")
    pt_weeks_required = None
    pt_sessions_required = None

    if "6 weeks" in context_text or "6 WEEKS" in context_text:
        pt_weeks_required = 6
    elif "4 weeks" in context_text:
        pt_weeks_required = 4

    if "minimum 6 sessions" in context_text or "6 sessions" in context_text:
        pt_sessions_required = 6

    if "physical therapy" in doc_text or "Physical therapy" in " ".join(doc_requirements):
        conditions = [
            {
                "field": "pt_attempted",
                "operator": "eq",
                "value": True
            }
        ]

        # Add duration requirement if found in context
        if pt_weeks_required:
            conditions.append({
                "field": "pt_duration_weeks",
                "operator": "gte",
                "value": pt_weeks_required
            })

        rules_list.append({
            "id": "physical_therapy_requirement",
            "description": f"Physical therapy must be attempted and documented{f' (minimum {pt_weeks_required} weeks)' if pt_weeks_required else ''}",
            "logic": "all",
            "conditions": conditions
        })

    # Rule 3: Medication trial
    if "medication" in doc_text or "nsaid" in context_text.lower():
        # Check if failure is required
        requires_failure = "failed" in context_text.lower() or "no relief" in context_text.lower()

        conditions = [
            {
                "field": "nsaid_documented",
                "operator": "eq",
                "value": True
            }
        ]

        if requires_failure:
            conditions.append({
                "field": "nsaid_failed",
                "operator": "eq",
                "value": True
            })

        rules_list.append({
            "id": "medication_trial_requirement",
            "description": f"Medication trial must be documented{' and failed' if requires_failure else ''}",
            "logic": "all",
            "conditions": conditions
        })

    # Rule 4: Clinical documentation timeframe
    if "within 30 days" in doc_text or "30 days" in doc_text:
        rules_list.append({
            "id": "recent_clinical_notes",
            "description": "Clinical notes must be within 30 days",
            "logic": "all",
            "conditions": [
                {
                    "field": "validation_passed",
                    "operator": "eq",
                    "value": True
                }
            ]
        })

    # Rule 5: Symptom duration requirement
    if "symptom" in context_text.lower() and ("weeks" in context_text or "months" in context_text):
        # Try to extract minimum duration
        # Common patterns: "6 weeks", "3 months", etc.
        import re

        # Look for patterns like "at least X weeks" or "minimum X months"
        duration_match = re.search(r'(\d+)\s*(weeks?|months?)', context_text.lower())
        if duration_match:
            number = int(duration_match.group(1))
            unit = duration_match.group(2)

            if 'month' in unit:
                rules_list.append({
                    "id": "symptom_duration_requirement",
                    "description": f"Symptoms must persist for at least {number} months",
                    "logic": "all",
                    "conditions": [
                        {
                            "field": "symptom_duration_months",
                            "operator": "gte",
                            "value": number
                        }
                    ]
                })
            elif 'week' in unit and number >= 6:  # Only add if significant duration
                rules_list.append({
                    "id": "symptom_duration_requirement",
                    "description": f"Symptoms must persist for at least {number} weeks",
                    "logic": "all",
                    "conditions": [
                        {
                            "field": "symptom_duration_weeks",
                            "operator": "gte",
                            "value": number
                        }
                    ]
                })

    # Rule 6: Evidence quality check (always include)
    rules_list.append({
        "id": "evidence_quality",
        "description": "Evidence must be validated with no hallucinations",
        "logic": "all",
        "conditions": [
            {
                "field": "hallucinations_detected",
                "operator": "eq",
                "value": 0
            },
            {
                "field": "validation_passed",
                "operator": "eq",
                "value": True
            }
        ]
    })

    return rules_list


def normalize_policy_criteria_manual(criteria: dict, custom_rules: list = None) -> list:
    """
    Manual rule specification for your insurance policies.

    Use this when you want full control over the rules being evaluated.

    Example usage:
    rules = normalize_policy_criteria_manual(policy_json, custom_rules=[
        {
            "id": "pt_duration",
            "description": "PT must be at least 6 weeks",
            "logic": "all",
            "conditions": [
                {"field": "pt_duration_weeks", "operator": "gte", "value": 6}
            ]
        }
    ])
    """
    if custom_rules:
        return custom_rules

    # Default rules based on common insurance requirements
    return [
        {
            "id": "imaging_required",
            "description": "Imaging must be documented within 2 months",
            "logic": "all",
            "conditions": [
                {"field": "imaging_documented", "operator": "eq", "value": True},
                {"field": "imaging_months_ago", "operator": "lte", "value": 2}
            ]
        },
        {
            "id": "conservative_therapy",
            "description": "Conservative therapy must be attempted",
            "logic": "all",
            "conditions": [
                {"field": "pt_attempted", "operator": "eq", "value": True},
                {"field": "nsaid_documented", "operator": "eq", "value": True}
            ]
        },
        {
            "id": "evidence_quality",
            "description": "Evidence must be validated",
            "logic": "all",
            "conditions": [
                {"field": "validation_passed", "operator": "eq", "value": True},
                {"field": "hallucinations_detected", "operator": "eq", "value": 0}
            ]
        }
    ]


# ============================================================================
# UTILITY FUNCTIONS FOR NORMALIZERS
# ============================================================================

def compare_normalized_data(patient_norm: dict, policy_rules: list) -> dict:
    """
    Convenience function to compare normalized patient data against policy rules.

    This wraps the rule engine's evaluate_all function.

    Args:
        patient_norm: Normalized patient evidence dictionary
        policy_rules: List of normalized policy rules

    Returns:
        Dictionary with evaluation results including:
        - results: List of individual rule results
        - all_criteria_met: Boolean indicating if all rules passed
        - total_rules: Count of total rules evaluated
        - rules_met: Count of rules that passed
        - rules_failed: Count of rules that failed
    """
    from app.rules.rule_engine import evaluate_all
    return evaluate_all(patient_norm, policy_rules)


def validate_normalized_patient(patient_norm: dict) -> tuple[bool, list]:
    """
    Validate that normalized patient data has all required fields.

    Args:
        patient_norm: Normalized patient evidence dictionary

    Returns:
        Tuple of (is_valid, missing_fields)
    """
    required_fields = [
        "symptom_duration_months",
        "pt_attempted",
        "nsaid_documented",
        "imaging_documented",
        "validation_passed",
        "hallucinations_detected"
    ]

    missing = []
    for field in required_fields:
        if field not in patient_norm:
            missing.append(field)

    return len(missing) == 0, missing


def validate_normalized_rules(policy_rules: list) -> tuple[bool, list]:
    """
    Validate that normalized policy rules are well-formed.

    Args:
        policy_rules: List of normalized policy rules

    Returns:
        Tuple of (is_valid, validation_errors)
    """
    errors = []

    if not isinstance(policy_rules, list):
        return False, ["Policy rules must be a list"]

    for i, rule in enumerate(policy_rules):
        if not isinstance(rule, dict):
            errors.append(f"Rule {i} is not a dictionary")
            continue

        # Check required fields
        if "id" not in rule:
            errors.append(f"Rule {i} missing 'id' field")
        if "description" not in rule:
            errors.append(f"Rule {i} missing 'description' field")
        if "conditions" not in rule:
            errors.append(f"Rule {i} missing 'conditions' field")
        elif not isinstance(rule["conditions"], list):
            errors.append(f"Rule {i} 'conditions' must be a list")
        else:
            # Validate each condition
            for j, condition in enumerate(rule["conditions"]):
                if not isinstance(condition, dict):
                    errors.append(f"Rule {i}, condition {j} is not a dictionary")
                    continue

                if "field" not in condition:
                    errors.append(f"Rule {i}, condition {j} missing 'field'")
                if "operator" not in condition:
                    errors.append(f"Rule {i}, condition {j} missing 'operator'")
                if "value" not in condition:
                    errors.append(f"Rule {i}, condition {j} missing 'value'")

    return len(errors) == 0, errors


def get_normalization_summary(patient_norm: dict) -> str:
    """
    Generate a human-readable summary of normalized patient data.

    Args:
        patient_norm: Normalized patient evidence dictionary

    Returns:
        Formatted string summary
    """
    lines = ["=== Patient Evidence Summary ==="]

    # Symptoms
    if patient_norm.get("symptom_duration_months"):
        lines.append(f"Symptom Duration: {patient_norm['symptom_duration_months']} months ({patient_norm.get('symptom_duration_weeks', 0)} weeks)")

    # Conservative therapy
    lines.append("\nConservative Therapy:")
    if patient_norm.get("pt_attempted"):
        duration = patient_norm.get("pt_duration_weeks", "Unknown")
        lines.append(f"  ✓ Physical Therapy: {duration} weeks")
    else:
        lines.append("  ✗ Physical Therapy: Not attempted")

    if patient_norm.get("nsaid_documented"):
        outcome = patient_norm.get("nsaid_outcome", "Unknown")
        lines.append(f"  ✓ NSAIDs: {outcome}")
    else:
        lines.append("  ✗ NSAIDs: Not documented")

    # Imaging
    lines.append("\nImaging:")
    if patient_norm.get("imaging_documented"):
        img_type = patient_norm.get("imaging_type", "Unknown")
        months_ago = patient_norm.get("imaging_months_ago", "Unknown")
        lines.append(f"  ✓ {img_type}: {months_ago} months ago")
    else:
        lines.append("  ✗ No imaging documented")

    # Validation
    lines.append("\nData Quality:")
    lines.append(f"  Validation: {'✓ Passed' if patient_norm.get('validation_passed') else '✗ Failed'}")
    lines.append(f"  Hallucinations: {patient_norm.get('hallucinations_detected', 0)}")

    return "\n".join(lines)