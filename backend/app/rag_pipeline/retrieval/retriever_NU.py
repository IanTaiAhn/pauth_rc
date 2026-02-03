import numpy as np


def mmr(ranked_list, query_embedding, lambda_mult=0.7, top_k=5):
    # very small MMR implementation wrapper for metadata list
    # ranked_list: list of dict {"embedding": , "metadata": }
    if not ranked_list:
        return []

    selected = []
    candidates = ranked_list.copy()

    # precompute similarities
    embs = np.vstack([c['embedding'] for c in candidates])
    q = np.array(query_embedding)
    from numpy.linalg import norm
    def cos(a,b):
        return np.dot(a,b) / (norm(a)*norm(b)+1e-12)

    sims = [cos(q, e) for e in embs]
    # naive greedy pick
    selected_idx = []
    while len(selected_idx) < min(top_k, len(candidates)):
        best = None
        best_score = -1e9
        for i, c in enumerate(candidates):
            if i in selected_idx:
                continue
            relevance = sims[i]
            diversity = 0
            for si in selected_idx:
                diversity = max(diversity, cos(embs[si], embs[i]))
            score = lambda_mult * relevance - (1 - lambda_mult) * diversity
            if score > best_score:
                best_score = score
                best = i
        selected_idx.append(best)
    out = [candidates[i] for i in selected_idx]
    return out


class Retriever:
    def __init__(self, embedder, store, top_k=8):
        self.embedder = embedder
        self.store = store
        self.top_k = top_k

    def retrieve(self, query: str):
        q_emb = self.embedder.embed([query])[0]
        raw = self.store.query(q_emb, top_k=self.top_k*3)  # retrieve more for reranking/MMR
        # attach embeddings to raw (if metadata contains embedding skip recompute)
        enriched = []
        for r in raw:
            meta = r['metadata']
            emb = meta.get('embedding')
            if emb is None:
                # fallback: we could store embeddings in meta; for now assume not
                emb = None
            enriched.append({"score": r['score'], "metadata": meta, "embedding": emb})
        # run mmr if embeddings present (otherwise simple top-k)
        with_emb = [e for e in enriched if e['embedding'] is not None]
        if with_emb:
            selected = mmr(with_emb, q_emb, top_k=5)
        else:
            selected = enriched[:5]
        return selected