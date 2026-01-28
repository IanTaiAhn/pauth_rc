"""
Custom normalization functions for your specific JSON formats
"""

from typing import Any, Dict, List


def normalize_patient_evidence(evidence: dict) -> dict:
    """
    Normalize YOUR specific patient chart JSON format.
    
    Input format:
    {
      "timestamp": "...",
      "analysis": {
        "requirements": {
          "symptom_duration_months": 4,
          "conservative_therapy": {...},
          "imaging": {...},
          ...
        }
      }
    }
    """
    normalized = {}
    
    # Extract the requirements section (where all the data lives)
    requirements = evidence.get("analysis", {}).get("requirements", {})
    
    # Symptom duration
    symptom_months = requirements.get("symptom_duration_months")
    if symptom_months is not None:
        normalized["symptom_duration_months"] = symptom_months
        normalized["symptom_duration_weeks"] = symptom_months * 4  # Convert to weeks
    
    # Conservative therapy
    conservative = requirements.get("conservative_therapy", {})
    
    # Physical therapy
    pt = conservative.get("physical_therapy", {})
    normalized["pt_attempted"] = pt.get("attempted", False)
    normalized["pt_duration_weeks"] = pt.get("duration_weeks")
    
    # NSAIDs
    nsaids = conservative.get("nsaids", {})
    normalized["nsaid_documented"] = nsaids.get("documented", False)
    normalized["nsaid_outcome"] = nsaids.get("outcome")
    normalized["nsaid_failed"] = nsaids.get("outcome") == "failed"
    
    # Injections
    injections = conservative.get("injections", {})
    normalized["injection_documented"] = injections.get("documented", False)
    normalized["injection_outcome"] = injections.get("outcome")
    normalized["injection_failed"] = injections.get("outcome") == "failed"
    
    # Imaging
    imaging = requirements.get("imaging", {})
    normalized["imaging_documented"] = imaging.get("documented", False)
    normalized["imaging_type"] = imaging.get("type")
    normalized["imaging_body_part"] = imaging.get("body_part")
    normalized["imaging_months_ago"] = imaging.get("months_ago")
    
    # Functional impairment
    functional = requirements.get("functional_impairment", {})
    normalized["functional_impairment_documented"] = functional.get("documented", False)
    normalized["functional_impairment_description"] = functional.get("description")
    
    # Metadata
    metadata = requirements.get("_metadata", {})
    normalized["validation_passed"] = metadata.get("validation_passed", False)
    normalized["hallucinations_detected"] = metadata.get("hallucinations_detected", 0)
    
    # Evidence notes
    normalized["evidence_notes"] = requirements.get("evidence_notes", [])
    
    # Analysis level data
    analysis = evidence.get("analysis", {})
    normalized["score"] = analysis.get("score")
    normalized["missing_items"] = analysis.get("missing_items", [])
    
    return normalized


def normalize_policy_criteria(criteria: dict) -> list:
    """
    Normalize YOUR specific insurance policy JSON format.
    
    Input format:
    {
      "rules": {
        "payer": "Aetna",
        "cpt_code": "73721",
        "coverage_criteria": {
          "clinical_indications": [...],
          "prerequisites": [...],
          "documentation_requirements": [...]
        }
      }
    }
    
    Output: List of rules in standardized condition format
    """
    rules_list = []
    
    rules = criteria.get("rules", {})
    coverage = rules.get("coverage_criteria", {})
    
    # Extract payer and CPT for reference
    payer = rules.get("payer")
    cpt_code = rules.get("cpt_code")
    
    # Rule 1: Prerequisites - X-ray within 60 days
    prerequisites = coverage.get("prerequisites", [])
    if any("X-ray" in prereq or "x-ray" in prereq.lower() for prereq in prerequisites):
        # Check if mentions "60 days" or "within the past 60 days"
        if any("60 days" in prereq for prereq in prerequisites):
            rules_list.append({
                "id": "xray_requirement",
                "description": "Weight-bearing X-rays must be completed within 60 days",
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
                        "value": 2  # 60 days = ~2 months
                    }
                ]
            })
    
    # Rule 2: Conservative therapy attempted
    doc_requirements = coverage.get("documentation_requirements", [])
    if any("Physical therapy" in req or "physical therapy" in req for req in doc_requirements):
        rules_list.append({
            "id": "physical_therapy_requirement",
            "description": "Physical therapy must be attempted and documented",
            "logic": "all",
            "conditions": [
                {
                    "field": "pt_attempted",
                    "operator": "eq",
                    "value": True
                }
            ]
        })
    
    # Rule 3: Medication trial
    if any("Medication" in req or "medication" in req for req in doc_requirements):
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
    
    # Rule 4: Clinical documentation within 30 days
    if any("within 30 days" in req for req in doc_requirements):
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
    
    # Rule 5: No hallucinations in evidence
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