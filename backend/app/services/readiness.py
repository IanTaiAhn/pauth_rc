# I'm pretty sure this only works right now because in evidence i have assigned a number to the extract clinical facts.
# Yep, I need to make sure this compute_readiness gets based on the payer policy criteria.

def compute_readiness(evidence: dict) -> tuple[int, list]:
    score = 100
    issues = []

    # -----------------------------
    # 1. Symptom Duration
    # -----------------------------
    duration = evidence.get("symptom_duration_months")

    if duration is None or duration < 3:
        score -= 15
        issues.append({
            "name": "symptom_duration",
            "severity": "high",
            "suggestion": "Document symptom duration of at least 3 months."
        })

    # -----------------------------
    # 2. Conservative Therapy
    # -----------------------------
    therapies = evidence.get("conservative_therapy", {})
    documented_count = 0

    # Physical Therapy
    pt = therapies.get("physical_therapy", {})
    if pt.get("attempted") and pt.get("duration_weeks", 0) >= 6:
        documented_count += 1

    # NSAIDs
    nsaids = therapies.get("nsaids", {})
    if nsaids.get("documented"):
        documented_count += 1

    # Injections
    injections = therapies.get("injections", {})
    if injections.get("documented"):
        documented_count += 1

    if documented_count < 2:
        score -= 20
        issues.append({
            "name": "conservative_therapy",
            "severity": "high",
            "suggestion": "Document at least two conservative treatments (e.g., PT, NSAIDs, injections)."
        })

    # -----------------------------
    # 3. Imaging
    # -----------------------------
    imaging = evidence.get("imaging", {})
    if not imaging.get("documented"):
        score -= 20
        issues.append({
            "name": "imaging_missing",
            "severity": "high",
            "suggestion": "Add recent diagnostic imaging (e.g., MRI, X-ray)."
        })
    elif imaging.get("months_ago", 999) > 6:
        score -= 10
        issues.append({
            "name": "imaging_outdated",
            "severity": "medium",
            "suggestion": "Imaging is older than 6 months; consider updated study."
        })

    # -----------------------------
    # 4. Functional Impairment
    # -----------------------------
    func = evidence.get("functional_impairment", {})
    if not func.get("documented"):
        score -= 15
        issues.append({
            "name": "functional_impairment",
            "severity": "high",
            "suggestion": "Document how symptoms limit daily activities or mobility."
        })

    # -----------------------------
    # 5. Evidence Reliability
    # -----------------------------
    metadata = evidence.get("_metadata", {})
    if not metadata.get("validation_passed", True):
        score -= 10
        issues.append({
            "name": "validation_failed",
            "severity": "medium",
            "suggestion": "Extracted data failed validation. Review source documentation."
        })

    if metadata.get("hallucinations_detected", 0) > 0:
        score -= 10
        issues.append({
            "name": "hallucinations_detected",
            "severity": "medium",
            "suggestion": "Some extracted evidence may be unreliable. Verify chart text."
        })

    # Ensure score stays within bounds
    score = max(min(score, 100), 0)

    return score, issues


def compute_readiness_score_with_exceptions(
    evaluation_results: dict,
    exception_applied: str | None
) -> int:
    """
    Compute readiness score accounting for exceptions.

    Issue 6 Fix: Score should reflect actual criteria met, not be artificially
    deflated or inflated by exceptions. Exceptions affect verdict, not score.

    Rules:
    - Base score = (rules_met / total_rules) * 100
    - If Workers' Comp / Exclusion exception: 0 (case is excluded)
    - All other exceptions: use base score unchanged (exception bypasses rules
      but doesn't change the numeric readiness percentage)
    """
    total_rules = evaluation_results.get("total_rules", 0)
    rules_met = evaluation_results.get("rules_met", 0)

    if total_rules == 0:
        return 0

    base_score = int((rules_met / total_rules) * 100)

    if not exception_applied:
        return base_score

    if "Workers' Compensation" in exception_applied or "Exclusion" in exception_applied:
        return 0  # Excluded cases score 0 — wrong payer entirely

    # For Red Flag, Acute Trauma, etc.: exception bypasses standard rules but
    # does not change the score. The score still reflects criteria met.
    return base_score


def determine_verdict(
    readiness_score: int,
    exception_applied: str | None,
    rules_failed: int = 0
) -> str:
    """
    Determine verdict with explicit exception handling.

    Issue 6 Fix: Verdict must be derived from exception type first, then score.
    This prevents the contradictory state of "25% readiness → LIKELY_TO_APPROVE"
    being unexplained — instead, the exception is the explicit driver.

    Priority order:
    1. Exclusions (Workers' Comp) → EXCLUDED
    2. Red flag / Acute Trauma exceptions → LIKELY_TO_APPROVE (bypass standard rules)
    3. No exception — standard score thresholds:
       - 80%+ → LIKELY_TO_APPROVE
       - 60–79% → NEEDS_REVIEW
       - <60% → LIKELY_TO_DENY
    """
    if exception_applied:
        if "Workers' Compensation" in exception_applied or "Exclusion" in exception_applied:
            return "EXCLUDED"

        if "Red Flag" in exception_applied or "Acute Trauma" in exception_applied:
            # Exception pathway allows approval despite failed standard rules
            return "LIKELY_TO_APPROVE"

    # Standard scoring — no exception applied
    if readiness_score >= 80:
        return "LIKELY_TO_APPROVE"
    elif readiness_score >= 60:
        return "NEEDS_REVIEW"
    else:
        return "LIKELY_TO_DENY"


if __name__ == "__main__":
    evidence = {
        "symptom_duration_months": 4,
        "conservative_therapy": {
            "physical_therapy": {
                "attempted": True,          # true → True
                "duration_weeks": 8
            },
            "nsaids": {
                "documented": True,         # true → True
                "outcome": "no relief"
            },
            "injections": {
                "documented": False,        # false → False
                "outcome": None             # null → None
            }
        },
        "imaging": {
            "documented": True,
            "type": "MRI",
            "body_part": "right knee",
            "months_ago": 2
        },
        "functional_impairment": {
            "documented": True,
            "description": "unable to climb stairs or walk more than 10 minutes"
        },
        "evidence_notes": [
            "Patient reports 4 months of right knee pain.",
            "Tried physical therapy for 8 weeks with minimal improvement.",
            "NSAIDs provided no relief.",
            "MRI of right knee 2 months ago shows meniscal tear."
        ],
        "_metadata": {
            "hallucinations_detected": 0,
            "hallucinated_notes": [],
            "validation_passed": True       # true → True
        }
    }

    score, issues = compute_readiness(evidence)

    print("Readiness Score:", score)
    print("Issues:", issues)



# old
# def compute_readiness(evidence: dict) -> tuple[int, list]:
#     score = 100
#     missing = []

#     for key, item in evidence.items():
#         if not item["found"]:
#             score -= 15
#             missing.append({
#                 "name": key,
#                 "severity": "high",
#                 "suggestion": f"Add documentation for {key.replace('_', ' ')}."
#             })

#     return max(score, 0), missing

# Clinics trust systems they understand.
# This should be mostly rules-based, not “AI vibes”.
# This is how you reduce hallucinations.