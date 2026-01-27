from pathlib import Path
from sentence_transformers import CrossEncoder

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = BASE_DIR / "models" / "minilm_reranker"


# Rule-type importance weights
RULE_TYPE_WEIGHTS = {
    "coverage_criteria": 1.3,
    "diagnosis_requirement": 1.25,
    "clinical_findings": 1.2,
    "imaging_requirement": 1.15,
    "conservative_treatment": 1.2,
    "exceptions": 1.1,
    "prior_imaging": 1.05,
    "age_rules": 1.0,
    "not_medically_necessary": 0.8,   # demote unless specifically searching denials
    "documentation": 0.6,
    "admin": 0.4,
    "appendix": 0.3,
    "general": 0.9
}


CRITERIA_KEYWORDS = [
    "must",
    "required",
    "medically necessary",
    "all of the following",
    "at least",
    "completed",
    "documented",
    "within",
    "prior to"
]


class Reranker:
    def __init__(self, model_path: str = DEFAULT_MODEL_DIR):
        self.model = CrossEncoder(str(model_path))

    def keyword_boost(self, text: str) -> float:
        text_lower = text.lower()
        boost = 1.0
        for kw in CRITERIA_KEYWORDS:
            if kw in text_lower:
                boost += 0.03
        return min(boost, 1.15)  # cap boost

    def rerank(self, query: str, candidates: list, top_k: int = 5):
        if not candidates:
            return []

        pairs = [(query, c["metadata"]["text"]) for c in candidates]
        scores = self.model.predict(pairs)

        adjusted = []
        for c, base_score in zip(candidates, scores):
            meta = c["metadata"]
            rule_type = meta.get("rule_type", "general")
            text = meta.get("text", "")

            # Rule-type weighting
            type_weight = RULE_TYPE_WEIGHTS.get(rule_type, 1.0)

            # Criteria language boost
            kw_boost = self.keyword_boost(text)

            final_score = base_score * type_weight * kw_boost

            adjusted.append((c, final_score))

        ranked = sorted(adjusted, key=lambda x: x[1], reverse=True)

        return [r[0] for r in ranked[:top_k]]
