# I'm pretty sure this only works right now because in evidence i have assigned a number to the extract clinical facts.

def compute_readiness(evidence: dict) -> tuple[int, list]:
    score = 100
    missing = []

    for key, item in evidence.items():
        if not item["found"]:
            score -= 15
            missing.append({
                "name": key,
                "severity": "high",
                "suggestion": f"Add documentation for {key.replace('_', ' ')}."
            })

    return max(score, 0), missing

# Clinics trust systems they understand.
# This should be mostly rules-based, not “AI vibes”.
# This is how you reduce hallucinations.