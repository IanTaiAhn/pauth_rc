# import json
# import backend.app.rag_pipeline.scripts.build_index as build_index
# from backend.app.rag_pipeline.retrieval.retriever import Retriever
# from backend.app.rag_pipeline.retrieval.reranker import Reranker
# from backend.app.rag_pipeline.generation.prompt import build_prompt
# from backend.app.rag_pipeline.generation.generator import generate_with_context

# Updated policy_extraction.py
import json
import backend.app.rag_pipeline.scripts.build_index as build_index
from backend.app.rag_pipeline.retrieval.retriever import Retriever
from backend.app.rag_pipeline.retrieval.reranker import Reranker
from backend.app.rag_pipeline.generation.prompt import build_medical_policy_prompt
from backend.app.rag_pipeline.generation.generator import generate_with_context


def extract_policy_rules(payer: str, cpt_code: str, index_name="default"):
    """
    Extract structured medical policy rules for a given payer and CPT code
    """
    # Ensure correct index is loaded
    if (
        build_index.STORE is None or 
        build_index.EMBEDDER is None or
        build_index.CURRENT_INDEX != index_name
    ):
        build_index.load_index(index_name)
        build_index.CURRENT_INDEX = index_name

    # 🔍 Enhanced retrieval query
    query = (
        f"{payer} CPT {cpt_code} medical necessity coverage criteria "
        f"requirements prior authorization documentation"
    )

    # Retrieve candidates
    retriever = Retriever(build_index.EMBEDDER, build_index.STORE, top_k=20)
    candidates = retriever.retrieve(query)
    print(f'✓ Retrieved {len(candidates)} candidate chunks')
    
    if not candidates:
        return {
            "rules": {"error": "No relevant policy documents found"},
            "context": [],
            "raw_output": ""
        }

    # Rerank
    reranker = Reranker()
    reranked = reranker.rerank(query, candidates, top_k=8)
    print(f'✓ Reranked to top {len(reranked)} chunks')

    # 🧠 Build medical-specific prompt
    prompt = build_medical_policy_prompt(reranked, payer, cpt_code)
    print('✓ Built medical policy extraction prompt')

    # Generate with higher token limit for medical policies
    raw_output = generate_with_context(prompt, max_new_tokens=256) # maybe change back to 800
    print('✓ Generated policy extraction')
    
    if not raw_output:
        return {
            "rules": {"error": "Generation failed"},
            "context": [],
            "raw_output": ""
        }

    # 🧾 Parse JSON safely with fallback
    try:
        # Try to find JSON in the output (in case of extra text)
        json_start = raw_output.find('{')
        json_end = raw_output.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = raw_output[json_start:json_end]
            rules_json = json.loads(json_str)
        else:
            rules_json = json.loads(raw_output)
            
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parsing failed: {e}")
        rules_json = {
            "error": "Model did not return valid JSON",
            "parse_error": str(e),
            "raw_output": raw_output[:500]  # First 500 chars for debugging
        }

    # Format context as STRINGS to match Pydantic model
    context_chunks = [
        f"[{c['metadata'].get('doc_id','unknown')}:{c['metadata'].get('chunk_id','?')}] "
        f"{c['metadata'].get('text') or c['metadata'].get('chunk_text', '')[:300]}..."
        for c in reranked
    ]

    return {
        "rules": rules_json,
        "context": context_chunks,  # Now list of strings
        "raw_output": raw_output
    }


if __name__ == "__main__":
    result = extract_policy_rules("Aetna", "73721")
    
    print("\n" + "="*60)
    print("EXTRACTED POLICY RULES")
    print("="*60)
    print(json.dumps(result["rules"], indent=2))
    
    print("\n" + "="*60)
    print("SOURCE CONTEXT")
    print("="*60)
    for i, ctx in enumerate(result["context"][:3]):  # Show first 3
        print(f"\n[{i+1}] Doc: {ctx['doc_id']}, Chunk: {ctx['chunk_id']}, Score: {ctx['score']:.3f}")
        print(f"Text: {ctx['text'][:200]}...")


# def extract_policy_rules(payer: str, cpt_code: str, index_name="default"):
#     # Ensure correct index is loaded
#     if (
#         build_index.STORE is None or 
#         build_index.EMBEDDER is None or
#         build_index.CURRENT_INDEX != index_name
#     ):
#         build_index.load_index(index_name)
#         build_index.CURRENT_INDEX = index_name

#     # 🔍 Retrieval query focused on criteria
#     query = f"{payer} CPT {cpt_code} medical necessity coverage criteria requirements"

#     retriever = Retriever(build_index.EMBEDDER, build_index.STORE, top_k=20)
#     candidates = retriever.retrieve(query)
#     print('retrieved the vectors to use...')

#     reranker = Reranker()
#     reranked = reranker.rerank(query, candidates, top_k=8)
#     print('reranked the retrieved vectors to 8...')

#     # 🧠 Build STRUCTURED EXTRACTION prompt (no question anymore)
#     prompt = build_prompt(reranked)
#     print('building_prompt...')

#     full_output = generate_with_context(prompt)
#     print('generating answer...')

#     # 🧾 Parse JSON safely
#     try:
#         rules_json = json.loads(full_output)
#     except json.JSONDecodeError:
#         rules_json = {
#             "error": "Model did not return valid JSON",
#             "raw_output": full_output
#         }

#     context_chunks = [
#         f"[{c['metadata'].get('doc_id','unknown')}:{c['metadata'].get('chunk_id','?')}] "
#         f"{c['metadata'].get('text') or c['metadata'].get('chunk_text') or ''}"
#         for c in reranked
#     ]

#     return {
#         "rules": rules_json,
#         "context": context_chunks,
#         "raw_output": full_output
#     }


# if __name__ == "__main__":
#     result = extract_policy_rules("Aetna", "73721")
#     print(json.dumps(result["rules"], indent=2))


