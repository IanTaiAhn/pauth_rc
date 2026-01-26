import os
import faiss
import numpy as np
import pickle
from typing import List, Dict

from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
INDEX_PATH = Path(os.getenv("VECTOR_STORE_PATH", CURRENT_DIR.parent / "vectorstore"))

class FaissStore:
    def __init__(self, dim: int):
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)
        self.metadatas = []

    def add(self, vectors: List[np.ndarray], metadatas: List[Dict]):
        arr = np.vstack(vectors).astype('float32')
        faiss.normalize_L2(arr)
        self.index.add(arr)
        self.metadatas.extend(metadatas)

    def save(self, path: str = INDEX_PATH, name: str = "index"):
        """
        Save the FAISS index and metadata using a dynamic name.
        Example:
            name="policies_2025" → policies_2025.faiss, policies_2025_meta.pkl
        """
        os.makedirs(path, exist_ok=True)

        index_path = f"{path}/{name}.faiss"
        meta_path = f"{path}/{name}_meta.pkl"

        faiss.write_index(self.index, index_path)

        with open(meta_path, "wb") as f:
            pickle.dump(self.metadatas, f)

        print(f"Saved FAISS index to {index_path}")
        print(f"Saved metadata to {meta_path}")

    @classmethod
    def load(cls, dim: int, path: str = INDEX_PATH, name: str = "index"):
        inst = cls(dim)

        index_path = f"{path}/{name}.faiss"
        meta_path = f"{path}/{name}_meta.pkl"

        inst.index = faiss.read_index(index_path)

        with open(meta_path, "rb") as f:
            inst.metadatas = pickle.load(f)

        return inst
    
    def query(self, vector, top_k: int = 5):
        v = np.array(vector).astype('float32')
        faiss.normalize_L2(v.reshape(1, -1))
        D, I = self.index.search(v.reshape(1, -1), top_k)
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            meta = self.metadatas[idx]
            results.append({"score": float(score), "metadata": meta})
        return results