"""
Normalization utilities for converting various JSON formats to canonical structure.
"""

from typing import Any, Dict, List


def normalize_patient_evidence(evidence: dict) -> dict:
    """
    Flatten patient evidence into a single-level dict with consistent field names.
    
    This function should be customized based on your actual patient chart JSON structure.
    The goal is to create a flat dictionary that the rule engine can easily navigate.
    """
    normalized = {}
    
    # Handle diagnoses (various possible formats)
    if "diagnosis" in evidence:
        normalized["diagnoses"] = evidence["diagnosis"] if isinstance(evidence["diagnosis"], list) else [evidence["diagnosis"]]
    elif "diagnoses" in evidence:
        normalized["diagnoses"] = evidence["diagnoses"] if isinstance(evidence["diagnoses"], list) else [evidence["diagnoses"]]
    elif "icd10_codes" in evidence:
        normalized["diagnoses"] = evidence["icd10_codes"] if isinstance(evidence["icd10_codes"], list) else [evidence["icd10_codes"]]
    else:
        normalized["diagnoses"] = []
    
    # Handle symptom duration
    if "symptom_duration_weeks" in evidence:
        normalized["symptom_duration_weeks"] = evidence["symptom_duration_weeks"]
    elif "symptoms" in evidence and isinstance(evidence["symptoms"], dict):
        normalized["symptom_duration_weeks"] = evidence["symptoms"].get("duration_weeks")
    
    # Handle conservative therapy - physical therapy
    if "conservative_therapy" in evidence:
        ct = evidence["conservative_therapy"]
        if isinstance(ct, dict):
            pt = ct.get("physical_therapy", {})
            normalized["pt_completed_weeks"] = pt.get("completed_weeks")
            normalized["pt_sessions"] = pt.get("sessions")
            
            # NSAID information
            nsaids = ct.get("nsaids", {})
            normalized["nsaid_trial"] = nsaids.get("trialed", False)
            normalized["nsaid_failed"] = nsaids.get("outcome") == "no relief"
    
    # Handle therapy at top level
    if "physical_therapy" in evidence:
        pt = evidence["physical_therapy"]
        if isinstance(pt, dict):
            normalized["pt_completed_weeks"] = pt.get("weeks") or pt.get("completed_weeks")
            normalized["pt_sessions"] = pt.get("sessions")
    
    if "medications" in evidence:
        meds = evidence["medications"]
        if isinstance(meds, list):
            normalized["medications"] = meds
            # Check for NSAIDs in medication list
            normalized["nsaid_trial"] = any("nsaid" in m.lower() or "ibuprofen" in m.lower() or "naproxen" in m.lower() 
                                           for m in meds if isinstance(m, str))
    
    # Handle imaging
    if "imaging" in evidence:
        img = evidence["imaging"]
        if isinstance(img, dict):
            mri = img.get("mri", {})
            normalized["mri_done"] = mri.get("done", False)
            normalized["mri_done_months_ago"] = mri.get("months_ago")
            normalized["mri_findings"] = mri.get("findings")
            
            xray = img.get("xray", {})
            normalized["xray_done"] = xray.get("done", False)
            normalized["xray_findings"] = xray.get("findings")
    
    # Handle any other top-level fields
    for key, value in evidence.items():
        if key not in normalized and not isinstance(value, dict):
            normalized[key] = value
    
    return normalized


def normalize_policy_criteria(criteria: dict) -> list:
    """
    Convert policy criteria into list of rules with standardized format.
    
    Expected format:
    {
        "criteria": [
            {
                "id": "rule_1",
                "description": "...",
                "requirement": {...}
            }
        ]
    }
    
    Output format:
    [
        {
            "id": "rule_1",
            "description": "...",
            "logic": "all",
            "conditions": [
                {"field": "...", "operator": "...", "value": ...}
            ]
        }
    ]
    """
    rules = []
    
    criteria_list = criteria.get("criteria", [])
    
    for rule in criteria_list:
        rule_id = rule.get("id", f"rule_{len(rules)}")
        description = rule.get("description", "No description")
        requirement = rule.get("requirement", {})
        logic = rule.get("logic", "all")  # default to all conditions must pass
        
        conditions = []
        
        # Convert requirements into conditions
        
        # Symptom duration
        if "symptom_duration_weeks" in requirement:
            duration_req = requirement["symptom_duration_weeks"]
            if isinstance(duration_req, dict):
                if "min" in duration_req:
                    conditions.append({
                        "field": "symptom_duration_weeks",
                        "operator": "gte",
                        "value": duration_req["min"]
                    })
                if "max" in duration_req:
                    conditions.append({
                        "field": "symptom_duration_weeks",
                        "operator": "lte",
                        "value": duration_req["max"]
                    })
            elif isinstance(duration_req, (int, float)):
                conditions.append({
                    "field": "symptom_duration_weeks",
                    "operator": "gte",
                    "value": duration_req
                })
        
        # Diagnosis requirements
        if "diagnosis_includes" in requirement:
            diagnoses = requirement["diagnosis_includes"]
            if isinstance(diagnoses, list):
                conditions.append({
                    "field": "diagnoses",
                    "operator": "any_in",
                    "value": diagnoses
                })
        
        if "diagnosis" in requirement:
            diagnoses = requirement["diagnosis"]
            if isinstance(diagnoses, list):
                conditions.append({
                    "field": "diagnoses",
                    "operator": "any_in",
                    "value": diagnoses
                })
            else:
                conditions.append({
                    "field": "diagnoses",
                    "operator": "contains",
                    "value": diagnoses
                })
        
        # Physical therapy requirements
        if "physical_therapy_weeks" in requirement:
            pt_req = requirement["physical_therapy_weeks"]
            if isinstance(pt_req, dict):
                if "min" in pt_req:
                    conditions.append({
                        "field": "pt_completed_weeks",
                        "operator": "gte",
                        "value": pt_req["min"]
                    })
                if "max" in pt_req:
                    conditions.append({
                        "field": "pt_completed_weeks",
                        "operator": "lte",
                        "value": pt_req["max"]
                    })
            elif isinstance(pt_req, (int, float)):
                conditions.append({
                    "field": "pt_completed_weeks",
                    "operator": "gte",
                    "value": pt_req
                })
        
        # NSAID requirements
        if "nsaid_trial_required" in requirement:
            if requirement["nsaid_trial_required"]:
                conditions.append({
                    "field": "nsaid_trial",
                    "operator": "eq",
                    "value": True
                })
        
        if "nsaid_failed" in requirement:
            if requirement["nsaid_failed"]:
                conditions.append({
                    "field": "nsaid_failed",
                    "operator": "eq",
                    "value": True
                })
        
        # MRI requirements
        if "mri_required" in requirement:
            if requirement["mri_required"]:
                conditions.append({
                    "field": "mri_done",
                    "operator": "eq",
                    "value": True
                })
        
        if "mri_max_months_ago" in requirement:
            conditions.append({
                "field": "mri_done_months_ago",
                "operator": "lte",
                "value": requirement["mri_max_months_ago"]
            })
        
        # Generic field matching
        for key, value in requirement.items():
            if key not in ["symptom_duration_weeks", "diagnosis_includes", "diagnosis",
                          "physical_therapy_weeks", "nsaid_trial_required", "nsaid_failed",
                          "mri_required", "mri_max_months_ago"]:
                # Handle as simple equality check
                if isinstance(value, dict) and "min" in value:
                    conditions.append({
                        "field": key,
                        "operator": "gte",
                        "value": value["min"]
                    })
                elif isinstance(value, dict) and "max" in value:
                    conditions.append({
                        "field": key,
                        "operator": "lte",
                        "value": value["max"]
                    })
                elif isinstance(value, dict) and "equals" in value:
                    conditions.append({
                        "field": key,
                        "operator": "eq",
                        "value": value["equals"]
                    })
                else:
                    conditions.append({
                        "field": key,
                        "operator": "eq",
                        "value": value
                    })
        
        if conditions:
            rules.append({
                "id": rule_id,
                "description": description,
                "logic": logic,
                "conditions": conditions
            })
    
    return rules