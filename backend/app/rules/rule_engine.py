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
    """
    if patient_value is None:
        return False
    
    if operator == "gte":
        return patient_value >= threshold
    elif operator == "gt":
        return patient_value > threshold
    elif operator == "lte":
        return patient_value <= threshold
    elif operator == "lt":
        return patient_value < threshold
    elif operator == "eq":
        return patient_value == threshold
    elif operator == "neq":
        return patient_value != threshold
    elif operator == "in":
        return patient_value in threshold
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
            "details": "No conditions specified"
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
    
    return {
        "rule_id": rule_id,
        "description": description,
        "met": met,
        "logic": logic,
        "condition_details": condition_details
    }


def evaluate_all(patient_data: dict, policy_rules: list) -> dict:
    """
    Evaluate all policy rules against patient data.
    
    Returns detailed report with overall decision.
    """
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
        "rules_failed": sum(1 for r in rule_results if not r["met"])
    }