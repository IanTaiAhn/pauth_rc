from pathlib import Path
from sentence_transformers import CrossEncoder

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/rag_pipeline
DEFAULT_MODEL_DIR = BASE_DIR / "models" / "minilm_reranker"

class Reranker:
    def __init__(self, model_path: str = DEFAULT_MODEL_DIR):
        self.model = CrossEncoder(str(model_path))


    def rerank(self, query: str, candidates: list, top_k: int = 5):
        pairs = [(query, c['metadata']['text']) for c in candidates]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [r[0] for r in ranked[:top_k]]
