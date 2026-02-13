"""
Custom normalization functions for your specific JSON formats
"""

from typing import Any, Dict, List


def normalize_patient_evidence(evidence: dict) -> dict:
    """
    Normalize YOUR specific patient chart JSON format.

    Handles THREE formats:

    Format 1 - Groq output with wrapper (legacy):
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

    Format 2 - Groq output flat structure (current):
    {
      "symptom_duration_months": 4,
      "conservative_therapy": {...},
      "imaging": {...},
      "_metadata": {...},
      ...
    }

    Format 3 - Pre-normalized (ready to use):
    {
      "normalized_data": {
        "symptom_duration_months": 4,
        "pt_attempted": true,
        ...
      },
      "metadata": {...}
    }

    Handles edge cases and ensures all fields have proper defaults.

    IMPROVED: Detects format and handles flat structure, wrapper structure, and pre-normalized data.
    """
    normalized = {}

    # DETECTION: Check if this is pre-normalized data (Format 3)
    if "normalized_data" in evidence:
        # Already normalized - just extract and return
        return evidence["normalized_data"]

    # DETECTION: Check if this is flat structure (Format 2) or wrapper structure (Format 1)
    # Flat structure has clinical fields at top level, wrapper has them in "requirements"
    if "requirements" in evidence:
        # Format 1 - wrapper structure (legacy)
        data_source = evidence.get("requirements", {})
    else:
        # Format 2 - flat structure (current)
        data_source = evidence

    # Symptom duration - handle both months and weeks
    symptom_months = data_source.get("symptom_duration_months")
    symptom_weeks = data_source.get("symptom_duration_weeks")

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
    conservative = data_source.get("conservative_therapy", {})

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
    imaging = data_source.get("imaging", {})
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
    functional = data_source.get("functional_impairment", {})
    normalized["functional_impairment_documented"] = functional.get("documented", False)
    normalized["functional_impairment_description"] = functional.get("description")

    # Clinical indication - extract from evidence_notes
    # Look for clinical diagnoses or physical exam findings that map to payer indications
    # Common patterns: "meniscal tear", "ligament rupture", "mechanical symptoms", etc.
    evidence_notes = data_source.get("evidence_notes", [])
    clinical_indication = None

    # Search through evidence notes for clinical indications
    # This is a simple keyword-based extraction; more sophisticated NLP could be added later
    evidence_text = " ".join(evidence_notes).lower() if isinstance(evidence_notes, list) else ""

    # Map common clinical findings to standardized indications
    indication_keywords = {
        "meniscal tear": ["meniscal tear", "meniscus tear", "torn meniscus"],
        "mechanical symptoms": ["mechanical", "catching", "locking", "clicking", "popping"],
        "ligament rupture": ["acl", "pcl", "mcl", "lcl", "ligament", "cruciate", "collateral"],
        "instability": ["instability", "giving way", "unstable"],
        "traumatic injury": ["trauma", "traumatic", "acute injury", "fall", "accident"],
        "positive mcmurray": ["mcmurray", "thessaly", "apley"],
        "post-operative": ["post-op", "post-surgical", "post surgery", "postoperative"],
        "red flag": ["infection", "tumor", "fracture", "cancer", "septic"]
    }

    # Find the first matching indication
    for indication, keywords in indication_keywords.items():
        if any(keyword in evidence_text for keyword in keywords):
            clinical_indication = indication
            break

    normalized["clinical_indication"] = clinical_indication

    # Metadata - ensure defaults
    metadata = data_source.get("_metadata", {})
    normalized["validation_passed"] = metadata.get("validation_passed", False)
    normalized["hallucinations_detected"] = metadata.get("hallucinations_detected", 0)

    # Evidence notes
    normalized["evidence_notes"] = data_source.get("evidence_notes", [])

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

    Handles THREE formats:

    Format 1 - Full policy result with wrapper (from RAG pipeline):
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

    Format 2 - Direct policy object (from orchestration router):
    {
      "payer": "Aetna",
      "cpt_code": "73721",
      "coverage_criteria": {
        "clinical_indications": [...],
        "prerequisites": [...],
        "documentation_requirements": [...]
      }
    }

    Format 3 - Pre-normalized (ready to use):
    {
      "rules": [
        {
          "id": "imaging_requirement",
          "description": "...",
          "logic": "all",
          "conditions": [...]
        }
      ],
      "metadata": {...}
    }

    Output: List of rules in standardized condition format

    IMPROVED: Detects format and handles Groq output, direct policy object, and pre-normalized data.
    """
    import re
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"normalize_policy_criteria called with keys: {list(criteria.keys())}")

    rules_list = []

    # DETECTION: Check if this is pre-normalized (Format 3)
    # Pre-normalized data has "rules" as a list, not a dict
    if "rules" in criteria and isinstance(criteria["rules"], list):
        logger.info(f"Rules already normalized (Format 3), returning {len(criteria['rules'])} rules")
        # Rules are already in the correct format - just validate and return
        for rule in criteria["rules"]:
            if isinstance(rule, dict) and "id" in rule and "conditions" in rule:
                rules_list.append(rule)
        return rules_list

    # DETECTION: Check if this is Format 1 (wrapper) or Format 2 (direct)
    # Format 1 has "rules" as a dict containing the policy object
    # Format 2 directly IS the policy object (has "coverage_criteria" at top level)
    if "coverage_criteria" in criteria:
        # Format 2 - Direct policy object (from orchestration router)
        policy_obj = criteria
        logger.info("Detected Format 2: Direct policy object")
    elif "rules" in criteria and isinstance(criteria["rules"], dict):
        # Format 1 - Wrapper structure (from RAG pipeline)
        policy_obj = criteria["rules"]
        logger.info("Detected Format 1: Wrapper structure")
    else:
        logger.warning(f"Unknown policy format. Keys: {list(criteria.keys())}")
        # Try to extract from rules key anyway
        policy_obj = criteria.get("rules", {})

    # Extract coverage criteria from the policy object
    coverage = policy_obj.get("coverage_criteria", {})
    logger.info(f"coverage_criteria keys: {list(coverage.keys()) if coverage else 'None'}")

    # Extract all text sources for intelligent parsing
    prerequisites = coverage.get("prerequisites", [])
    doc_requirements = coverage.get("documentation_requirements", [])
    # Context is only available in Format 1 (wrapper), not Format 2 (direct)
    context = criteria.get("context", [])

    logger.info(f"prerequisites: {prerequisites}")
    logger.info(f"doc_requirements count: {len(doc_requirements)}")
    logger.info(f"context type: {type(context)}, count: {len(context) if isinstance(context, list) else 'N/A'}")

    # Combine all text for pattern matching
    all_text = " ".join(
        prerequisites + doc_requirements + (context if isinstance(context, list) else [])
    )
    all_text_lower = all_text.lower()

    # =========================================================================
    # RULE 1: X-ray/Imaging Requirement
    # =========================================================================
    # Look for X-ray requirements in prerequisites
    for prereq in prerequisites:
        prereq_lower = prereq.lower()
        if "x-ray" in prereq_lower or "xray" in prereq_lower or "imaging" in prereq_lower:
            # Extract timeframe with multiple patterns
            imaging_months = 2  # default

            # Check for days
            days_match = re.search(r'(\d+)\s*days?', prereq_lower)
            if days_match:
                days = int(days_match.group(1))
                imaging_months = days / 30  # Convert to months

            # Check for months
            months_match = re.search(r'(\d+)\s*months?', prereq_lower)
            if months_match:
                imaging_months = int(months_match.group(1))

            # Check context for more specific timeframes
            if "60 days" in all_text_lower or "within 60 days" in all_text_lower:
                imaging_months = 2
            elif "90 days" in all_text_lower:
                imaging_months = 3
            elif "30 days" in all_text_lower:
                imaging_months = 1

            rules_list.append({
                "id": "xray_requirement",
                "description": f"Weight-bearing X-rays must be completed within {int(imaging_months * 30)} days",
                "logic": "all",
                "conditions": [
                    {
                        "field": "imaging_documented",
                        "operator": "eq",
                        "value": True
                    },
                    {
                        "field": "imaging_type",
                        "operator": "eq",
                        "value": "X-ray"
                    },
                    {
                        "field": "imaging_months_ago",
                        "operator": "lte",
                        "value": imaging_months
                    }
                ]
            })
            break  # Only add once

    # =========================================================================
    # RULE 2: Physical Therapy Requirement
    # =========================================================================
    # Check both prerequisites and documentation requirements
    pt_mentioned = False
    pt_weeks_required = None

    for text_source in prerequisites + doc_requirements:
        text_lower = text_source.lower()
        if "physical therapy" in text_lower or "pt" in text_lower:
            pt_mentioned = True

            # Look for duration in weeks
            weeks_match = re.search(r'(\d+)\s*weeks?', text_lower)
            if weeks_match:
                pt_weeks_required = int(weeks_match.group(1))

            # Also check context for "6 WEEKS" pattern
            if not pt_weeks_required and ("6 weeks" in all_text or "6 WEEKS" in all_text):
                pt_weeks_required = 6

    if pt_mentioned:
        conditions = [
            {
                "field": "pt_attempted",
                "operator": "eq",
                "value": True
            }
        ]

        description = "Physical therapy must be attempted and documented"
        if pt_weeks_required:
            description = f"Physical therapy must be attempted and documented (minimum {pt_weeks_required} weeks)"
            conditions.append({
                "field": "pt_duration_weeks",
                "operator": "gte",
                "value": pt_weeks_required
            })

        rules_list.append({
            "id": "physical_therapy_requirement",
            "description": description,
            "logic": "all",
            "conditions": conditions
        })

    # =========================================================================
    # RULE 3: Medication Trial Requirement
    # =========================================================================
    medication_mentioned = False
    for text_source in prerequisites + doc_requirements:
        text_lower = text_source.lower()
        if any(keyword in text_lower for keyword in ["medication", "nsaid", "analgesic"]):
            medication_mentioned = True
            break

    if medication_mentioned:
        rules_list.append({
            "id": "medication_trial_requirement",
            "description": "Medication trial must be documented",
            "logic": "all",
            "conditions": [
                {
                    "field": "nsaid_documented",
                    "operator": "eq",
                    "value": True
                }
            ]
        })

    # =========================================================================
    # RULE 4: Recent Clinical Notes Requirement
    # =========================================================================
    # Check for 30-day requirement in documentation requirements
    for doc_req in doc_requirements:
        doc_lower = doc_req.lower()
        if "30 days" in doc_lower or "within 30 days" in doc_lower:
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
            break

    # =========================================================================
    # RULE 5: Clinical Indication Requirement (CRITICAL GATING CRITERION)
    # =========================================================================
    # This checks if the patient has a valid clinical indication from the payer's list
    clinical_indications = coverage.get("clinical_indications", [])

    if clinical_indications:
        # Normalize the indications list for case-insensitive matching
        normalized_indications = []
        for indication in clinical_indications:
            indication_lower = indication.lower()
            # Map payer's indication text to our standardized keywords
            if "meniscal tear" in indication_lower or "meniscus" in indication_lower:
                normalized_indications.append("meniscal tear")
            elif "mechanical" in indication_lower:
                normalized_indications.append("mechanical symptoms")
            elif "ligament" in indication_lower or "acl" in indication_lower or "pcl" in indication_lower:
                normalized_indications.append("ligament rupture")
            elif "instability" in indication_lower:
                normalized_indications.append("instability")
            elif "traumatic" in indication_lower or "trauma" in indication_lower:
                normalized_indications.append("traumatic injury")
            elif "mcmurray" in indication_lower:
                normalized_indications.append("positive mcmurray")
            elif "post-operative" in indication_lower or "surgery" in indication_lower:
                normalized_indications.append("post-operative")
            elif "infection" in indication_lower or "tumor" in indication_lower or "fracture" in indication_lower or "red flag" in indication_lower:
                normalized_indications.append("red flag")

        # Only add the rule if we have normalized indications
        if normalized_indications:
            rules_list.append({
                "id": "clinical_indication_requirement",
                "description": f"Patient must have a valid clinical indication: {', '.join(set(normalized_indications))}",
                "logic": "all",
                "conditions": [
                    {
                        "field": "clinical_indication",
                        "operator": "in",
                        "value": normalized_indications
                    }
                ]
            })
            logger.info(f"Added clinical_indication_requirement rule with {len(normalized_indications)} allowed indications")

    # =========================================================================
    # RULE 6: Evidence Quality Check (ALWAYS INCLUDE)
    # =========================================================================

    # Log warning if no clinical rules were generated
    if len(rules_list) == 0:
        logger.warning(
            f"No clinical rules generated from policy. "
            f"Prerequisites: {prerequisites}, "
            f"Doc requirements count: {len(doc_requirements)}, "
            f"Context entries: {len(context) if isinstance(context, list) else 0}"
        )
    else:
        logger.info(f"Generated {len(rules_list)} clinical rules before evidence_quality rule")

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

    logger.info(f"Returning {len(rules_list)} total rules (including evidence_quality)")
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
        "clinical_indication",
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

    # Clinical indication
    clinical_indication = patient_norm.get("clinical_indication")
    if clinical_indication:
        lines.append(f"Clinical Indication: {clinical_indication}")
    else:
        lines.append("Clinical Indication: ✗ None identified")

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