# embeddings/embedder.py
# TODO Make this path work using other means than hardcoding it.backend\app\rag_pipeline\models\minilm
import os
from typing import List

# OPENAI = os.getenv("OPENAI_API_KEY") is not None

class BaseEmbedder:
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

from sentence_transformers import SentenceTransformer

class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(self, model_name: str = None):
        print('os from embedder.py: ', os.getcwd())
        # Default to local path instead of remote model name
        self.model_name = model_name or os.getenv("SENT_TRANSFORMER_MODEL", "backend/app/rag_pipeline/models/minilm")
        self.model = SentenceTransformer(self.model_name)

    def embed(self, texts: List[str]):
        return self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).tolist()

def get_embedder():
    return SentenceTransformerEmbedder()