from typing import Any, Dict, List, Optional


def get_nested_value(data: dict, path: str, default=None) -> Any:
    """
    Safely extract nested values from dict using dot notation.
    Example: get_nested_value(data, "therapy.physical.weeks") 
    """
    keys = path.split('.')
    value = data
    
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default
    
    return value


def compare_values(patient_value: Any, operator: str, threshold: Any) -> bool:
    """
    Compare patient value against threshold using specified operator.

    Operators:
    - gte: greater than or equal
    - gt: greater than
    - lte: less than or equal
    - lt: less than
    - eq: equal
    - neq: not equal
    - in: value in list
    - contains: list contains value
    - any_in: any overlap between lists

    IMPROVED: Better handling of None values and string comparisons
    """
    # Handle None values more intelligently
    if patient_value is None:
        # For equality checks, None can equal None or False
        if operator == "eq" and (threshold is None or threshold is False):
            return True
        return False

    # String comparison normalization for "eq" operator
    if operator == "eq" and isinstance(patient_value, str) and isinstance(threshold, str):
        # Case-insensitive comparison for string equality
        return patient_value.lower().strip() == threshold.lower().strip()

    if operator == "gte":
        try:
            return patient_value >= threshold
        except TypeError:
            return False
    elif operator == "gt":
        try:
            return patient_value > threshold
        except TypeError:
            return False
    elif operator == "lte":
        try:
            return patient_value <= threshold
        except TypeError:
            return False
    elif operator == "lt":
        try:
            return patient_value < threshold
        except TypeError:
            return False
    elif operator == "eq":
        return patient_value == threshold
    elif operator == "neq":
        return patient_value != threshold
    elif operator == "in":
        try:
            return patient_value in threshold
        except TypeError:
            return False
    elif operator == "contains":
        if isinstance(patient_value, list):
            return threshold in patient_value
        return False
    elif operator == "any_in":
        if isinstance(patient_value, list) and isinstance(threshold, list):
            return any(item in threshold for item in patient_value)
        return False
    else:
        raise ValueError(f"Unknown operator: {operator}")


def evaluate_condition(patient_data: dict, condition: dict) -> bool:
    """
    Evaluate a single condition against patient data.

    Condition format:
    {
        "field": "symptom_duration_weeks",
        "operator": "gte",
        "value": 6
    }
    """
    field = condition.get("field")
    operator = condition.get("operator")
    threshold = condition.get("value")

    if not all([field, operator]):
        return False

    patient_value = get_nested_value(patient_data, field)

    try:
        return compare_values(patient_value, operator, threshold)
    except Exception as e:
        print(f"Error evaluating condition {condition}: {e}")
        return False


def _format_patient_values(patient_values: List[Any], patient_data: dict) -> str:
    """
    Format patient values into a human-readable summary string.

    Handles different value types intelligently:
    - Strings: Join with commas
    - Numbers: Format appropriately (e.g., "6 weeks", "2 months")
    - Lists: Flatten and join
    - Booleans: Convert to Yes/No

    Args:
        patient_values: List of raw patient values from conditions
        patient_data: Full patient data dict for context

    Returns:
        Human-readable summary string
    """
    if not patient_values:
        return "Not found in chart"

    formatted_parts = []

    for value in patient_values:
        if value is None:
            continue
        elif isinstance(value, bool):
            formatted_parts.append("Yes" if value else "No")
        elif isinstance(value, (int, float)):
            # Try to add contextual units if possible
            # For now, just convert to string
            formatted_parts.append(str(value))
        elif isinstance(value, list):
            # Flatten lists and join
            list_items = [str(item) for item in value if item is not None]
            if list_items:
                formatted_parts.append(", ".join(list_items))
        elif isinstance(value, str):
            formatted_parts.append(value)
        else:
            formatted_parts.append(str(value))

    if not formatted_parts:
        return "Not found in chart"

    # Join all parts with semicolons for clarity
    return "; ".join(formatted_parts)


def evaluate_rule(patient_data: dict, rule: dict) -> dict:
    """
    Evaluate a complete rule with multiple conditions.

    Rule format:
    {
        "id": "rule_1",
        "description": "Patient must have 6+ weeks of symptoms",
        "logic": "all",  # or "any"
        "conditions": [...]
    }
    """
    rule_id = rule.get("id", "unknown")
    description = rule.get("description", "No description")
    logic = rule.get("logic", "all")
    conditions = rule.get("conditions", [])

    if not conditions:
        return {
            "rule_id": rule_id,
            "description": description,
            "met": False,
            "details": "No conditions specified",
            "patient_value": "Not found in chart"
        }

    results = [evaluate_condition(patient_data, cond) for cond in conditions]

    if logic == "all":
        met = all(results)
    elif logic == "any":
        met = any(results)
    else:
        met = False

    # Provide detailed feedback
    condition_details = []
    patient_values = []
    for i, (condition, result) in enumerate(zip(conditions, results)):
        field = condition.get("field")
        operator = condition.get("operator")
        threshold = condition.get("value")
        patient_value = get_nested_value(patient_data, field)

        condition_details.append({
            "condition": f"{field} {operator} {threshold}",
            "patient_value": patient_value,
            "met": result
        })

        # Collect patient values for summarization
        if patient_value is not None:
            patient_values.append(patient_value)

    # Generate a summarized patient_value string
    if not patient_values:
        summarized_patient_value = "Not found in chart"
    elif met:
        # For passing rules, concatenate the matched values into a readable string
        summarized_patient_value = _format_patient_values(patient_values, patient_data)
    else:
        # For failing rules, indicate what was found (if anything)
        summarized_patient_value = _format_patient_values(patient_values, patient_data) if patient_values else "Not found in chart"

    return {
        "rule_id": rule_id,
        "description": description,
        "met": met,
        "logic": logic,
        "condition_details": condition_details,
        "patient_value": summarized_patient_value
    }


class RepeatImagingRule:
    """
    Issue 9 Fix: Check if requesting imaging type already exists for the patient.

    When a patient already has recent imaging of the same modality as the requested
    CPT code, a warning is raised to prompt clinical review before ordering a new study.
    This prevents unnecessary $1,500+ imaging orders and missed opportunities to review
    existing studies for progression.

    Affected patients: 07 (Jasmine Tran), 10 (Tiffany Osei)
    Priority: P1 - HIGH
    """

    # CPT codes → imaging modality mapping
    MRI_CPTS = {"73721", "73722", "73723"}
    CT_CPTS = {"73700", "73701"}

    # Threshold: less than 6 months old triggers the warning
    RECENT_MONTHS_THRESHOLD = 6

    def __init__(self):
        self.id = "repeat_imaging_check"
        self.description = "Verify new imaging order when recent prior imaging exists"

    def _get_modality_from_cpt(self, cpt: str) -> str:
        """Map CPT code to imaging modality string."""
        if cpt in self.MRI_CPTS:
            return "MRI"
        elif cpt in self.CT_CPTS:
            return "CT"
        return "Unknown"

    def evaluate(self, normalized_patient: dict, requested_cpt: str) -> Optional[dict]:
        """
        Evaluate whether a repeat imaging warning should be issued.

        Returns a warning dict if the patient already has recent imaging of the
        same modality, or None if no conflict is detected.

        Args:
            normalized_patient: Normalized patient evidence dict
            requested_cpt: The CPT code being requested (e.g., "73721")

        Returns:
            Warning dict if repeat imaging detected, None otherwise.
        """
        imaging_type = normalized_patient.get("imaging_type")
        imaging_months_ago = normalized_patient.get("imaging_months_ago")

        # Cannot assess if imaging type or recency is unknown
        if imaging_type is None or imaging_months_ago is None:
            return None

        requested_modality = self._get_modality_from_cpt(requested_cpt)

        # Only warn if requesting the same modality that already exists recently
        if imaging_type.upper() == requested_modality.upper() and imaging_months_ago < self.RECENT_MONTHS_THRESHOLD:
            imaging_months_ago_display = round(imaging_months_ago, 1)
            return {
                "rule_id": self.id,
                "description": self.description,
                "warning": (
                    f"Patient already has a recent {imaging_type} from "
                    f"{imaging_months_ago_display} month(s) ago. "
                    f"Review existing imaging before ordering a new study."
                ),
                "recommendation": "REVIEW_EXISTING_IMAGING_FIRST",
                "severity": "WARNING",
                "imaging_type": imaging_type,
                "imaging_months_ago": imaging_months_ago_display,
            }

        return None


def evaluate_workers_compensation_exclusion(patient_data: dict) -> Optional[dict]:
    """
    Issue 7 Fix: Check if this is a Workers Compensation case before evaluating
    standard PA criteria. WC cases must be excluded — billing Medicaid/commercial
    insurance for a WC injury is a compliance violation.

    Returns an exclusion result dict if the case is excluded, None otherwise.
    """
    if patient_data.get("is_workers_compensation"):
        return {
            "rule_id": "workers_compensation_exclusion",
            "description": "Workers Compensation cases are excluded from standard PA evaluation",
            "met": False,
            "logic": "all",
            "condition_details": [
                {
                    "condition": "is_workers_compensation eq False",
                    "patient_value": True,
                    "met": False
                }
            ],
            "patient_value": "Workers Compensation case detected",
            "exclusion": True,
            "exclusion_reason": "Workers' Compensation — bill WC carrier, not standard payer"
        }
    return None


def evaluate_all(patient_data: dict, policy_rules: list, requested_cpt: str = "") -> dict:
    """
    Evaluate all policy rules against patient data.

    Issue 7 Fix: Workers Compensation exclusion is checked first. If the case
    is a WC case, standard PA rules are not evaluated and the result is EXCLUDED.

    Issue 9 Fix: Repeat imaging detection runs after WC exclusion. If the patient
    already has recent imaging of the same modality as the requested CPT code, a
    warning is added to the return value. The warning does not block evaluation —
    standard PA rules are still assessed — but it surfaces for clinician review.

    Args:
        patient_data: Normalized patient evidence dict
        policy_rules: List of normalized policy rule dicts
        requested_cpt: CPT code being requested (e.g., "73721"). Used only for
                       repeat imaging detection; safe to omit for legacy callers.

    Returns detailed report with overall decision.
    """
    # Issue 7: Check WC exclusion before running any standard rules
    wc_exclusion = evaluate_workers_compensation_exclusion(patient_data)
    if wc_exclusion is not None:
        return {
            "results": [wc_exclusion],
            "all_criteria_met": False,
            "total_rules": 1,
            "rules_met": 0,
            "rules_failed": 1,
            "excluded": True,
            "exclusion_reason": wc_exclusion["exclusion_reason"],
            "warnings": [],
        }

    # Issue 9: Check for repeat imaging before evaluating standard rules.
    # A warning is collected and returned alongside normal results; it does NOT
    # short-circuit evaluation because the PA may still be clinically justified.
    warnings: list[dict] = []
    if requested_cpt:
        repeat_imaging_warning = RepeatImagingRule().evaluate(patient_data, requested_cpt)
        if repeat_imaging_warning is not None:
            warnings.append(repeat_imaging_warning)

    rule_results = []

    for rule in policy_rules:
        result = evaluate_rule(patient_data, rule)
        rule_results.append(result)

    all_met = all(r["met"] for r in rule_results)

    return {
        "results": rule_results,
        "all_criteria_met": all_met,
        "total_rules": len(rule_results),
        "rules_met": sum(1 for r in rule_results if r["met"]),
        "rules_failed": sum(1 for r in rule_results if not r["met"]),
        "excluded": False,
        "exclusion_reason": None,
        "warnings": warnings,
    }