# generation/prompt.py
from typing import List


PROMPT_TEMPLATE = """
Use ONLY the context below to answer the question. If the context does not contain the answer, say "I cannot answer from the provided documents." Provide short, citation-backed answers. Cite chunks as [doc_id:chunk_id].

Context:
{context}

Question: {question}

Answer:
"""

def build_prompt(chunks: List[dict], question: str) -> str:
    ctx = []
    for c in chunks:
        md = c['metadata']
        # fallback to empty string if neither key exists
        text = md.get('text') or md.get('chunk_text') or ""
        src = f"[{md.get('doc_id','unknown')}:{md.get('chunk_id','?')}]"
        ctx.append(f"{src} {text}")
    context = "\n\n".join(ctx)
    return PROMPT_TEMPLATE.format(context=context, question=question)