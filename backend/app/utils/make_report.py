def build_authz_report(patient_norm: dict, policy_rules: list, evaluation: dict) -> str:
    """
    Build a comprehensive authorization report from normalized data and evaluation results.

    IMPROVED: Better formatting, more informative output, and clearer presentation.
    """
    lines = []

    lines.append("=" * 80)
    lines.append("PRIOR AUTHORIZATION RULE EVALUATION REPORT")
    lines.append("=" * 80)
    lines.append("")

    # ---------------------------
    # Normalized Patient Data
    # ---------------------------
    lines.append("📋 Normalized Patient Data:")
    lines.append("-" * 80)

    # Group related fields for better readability
    important_fields = [
        "symptom_duration_months",
        "symptom_duration_weeks",
        "pt_attempted",
        "pt_duration_weeks",
        "nsaid_documented",
        "nsaid_outcome",
        "nsaid_failed",
        "injection_documented",
        "injection_outcome",
        "injection_failed",
        "imaging_documented",
        "imaging_type",
        "imaging_body_part",
        "imaging_months_ago",
        "functional_impairment_documented",
        "functional_impairment_description",
        "validation_passed",
        "hallucinations_detected",
        "score",
        "missing_items"
    ]

    for key in important_fields:
        if key in patient_norm:
            lines.append(f"  {key}: {patient_norm[key]}")

    # Include any additional fields not in the important list
    for key, value in patient_norm.items():
        if key not in important_fields and key != "evidence_notes":
            lines.append(f"  {key}: {value}")

    # ---------------------------
    # Policy Rules
    # ---------------------------
    lines.append("")
    lines.append(f"📜 Extracted {len(policy_rules)} Rules from Policy:")
    lines.append("-" * 80)

    for rule in policy_rules:
        lines.append(f"\n  [{rule['id']}] {rule['description']}")
        for cond in rule["conditions"]:
            lines.append(f"    → {cond['field']} {cond['operator']} {cond['value']}")

    # ---------------------------
    # Evaluation Summary
    # ---------------------------
    lines.append("")
    lines.append("=" * 80)
    lines.append("🏥 PRIOR AUTHORIZATION EVALUATION RESULTS")
    lines.append("=" * 80)
    lines.append("")

    decision = "✅ APPROVED" if evaluation["all_criteria_met"] else "❌ DENIED"
    lines.append(decision)
    lines.append("")
    lines.append(f"Rules Met: {evaluation['rules_met']}/{evaluation['total_rules']}")

    # ---------------------------
    # Detailed Rule Results
    # ---------------------------
    lines.append("")
    lines.append("-" * 80)
    lines.append("Detailed Results:")
    lines.append("-" * 80)

    for result in evaluation["results"]:
        status = "✅" if result["met"] else "❌"
        lines.append(f"\n{status} [{result['rule_id']}] {result['description']}")

        for detail in result.get("condition_details", []):
            check = "  ✓" if detail["met"] else "  ✗"
            lines.append(f"{check} {detail['condition']}")
            lines.append(f"     Patient value: {detail['patient_value']}")

    return "\n".join(lines)
