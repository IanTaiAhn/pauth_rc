import backend.app.rag_pipeline.scripts.build_index as build_index
from backend.app.rag_pipeline.retrieval.retriever import Retriever
from backend.app.rag_pipeline.retrieval.reranker import Reranker
from backend.app.rag_pipeline.generation.prompt import build_prompt
from backend.app.rag_pipeline.generation.generator import generate_answer


def extract_answer(full_output: str) -> str:
    # Split on the last occurrence of "Answer:"
    if "Answer:" in full_output:
        return full_output.split("Answer:")[-1].strip()
    return full_output.strip()

def ask_question(query: str, index_name="default"):
    # If the requested index is not loaded, load it
    if (
        build_index.STORE is None or 
        build_index.EMBEDDER is None or
        build_index.CURRENT_INDEX != index_name
    ):
        build_index.load_index(index_name)
        build_index.CURRENT_INDEX = index_name

    retriever = Retriever(build_index.EMBEDDER, build_index.STORE, top_k=15)
    candidates = retriever.retrieve(query)

    reranker = Reranker()
    reranked = reranker.rerank(query, candidates, top_k=1)

    prompt = build_prompt(reranked, query)
    full_output = generate_answer(prompt)
    answer = extract_answer(full_output)

    context_chunks = [
        f"[{c['metadata'].get('doc_id','unknown')}:{c['metadata'].get('chunk_id','?')}] "
        f"{c['metadata'].get('text') or c['metadata'].get('chunk_text') or ''}"
        for c in reranked
    ]

    return {
        "answer": answer,
        "context": context_chunks,
        "raw_output": full_output
    }




if __name__ == "__main__":
    ask_question("What are the highlighted portions of this text?")
    