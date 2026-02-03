def normalize_policy_criteria(criteria: dict) -> list:
    normalized = []

    for rule in criteria["criteria"]:
        req = rule["requirement"]

        normalized.append({
            "id": rule["id"],
            "description": rule["description"],
            "checks": {
                "min_symptom_duration_weeks": req.get("symptom_duration_weeks", {}).get("min"),
                "required_diagnoses": req.get("diagnosis_includes"),
                "min_pt_weeks": req.get("physical_therapy_weeks", {}).get("min"),
            }
        })

    return normalized
