# idon't know if I want this since claude helped with this portion in the evidence code...
def build_justification(evidence: dict) -> str:
    parts = []

    if evidence["conservative_therapy"]["found"]:
        parts.append("The patient has undergone conservative management.")

    if evidence["duration_documented"]["found"]:
        parts.append(
            f"Treatment duration of {evidence['duration_documented']['value']} is documented."
        )

    parts.append(
        "Symptoms persist despite conservative treatment, warranting further evaluation."
    )

    return " ".join(parts)

# ⚠️ This avoids hallucination and legal risk.
# This is where:
# policy snippets improve tone
# LLM shines
# you sound “payer-native”...