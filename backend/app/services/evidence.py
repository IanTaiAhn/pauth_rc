def detect_conservative_therapy(text: str) -> dict:
    keywords = ["physical therapy", "pt", "chiropractic", "home exercise"]
    for kw in keywords:
        if kw in text.lower():
            return {
                "found": True,
                "evidence_text": kw,
                "confidence": 0.85
            }
    return {
        "found": False,
        "confidence": 0.9
    }
# You can later replace this with:
# LLM classification
# embeddings + retrieval
# hybrid rules
# But start simple and deterministic.



# Aggregator
# def extract_evidence(text: str) -> dict:
#     return {
#         "conservative_therapy": detect_conservative_therapy(text),
#         "duration_documented": detect_duration(text),
#         "failed_treatments": detect_failed_treatments(text),
#         "symptom_severity": detect_severity(text),
#         "recent_imaging": detect_imaging(text)
#     }
