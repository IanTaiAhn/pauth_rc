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
    # THIS IS COOL. I retrieve relevant chunks first.
    query = (
        f"{payer} CPT {cpt_code} coverage criteria clinical findings conservative treatment imaging requirements"
    )

    # Retrieve candidates
    retriever = Retriever(build_index.EMBEDDER, build_index.STORE, top_k=40)
    candidates = retriever.retrieve(query)
    print(f'✓ Retrieved {len(candidates)} candidate chunks')
    
    if not candidates:
        return {
            "rules": {"error": "No relevant policy documents found"},
            "context": [],
            "raw_output": ""
        }

    # Rerank 
    # With the specialized retrieved chunks I then rerank to get my top chunks.
    reranker = Reranker()
    reranked = reranker.rerank(query, candidates, top_k=10)
    print(f'✓ Reranked to top {len(reranked)} chunks')
    print("\n📚 TOP RERANKED CHUNKS SENT TO LLM:\n")
    for i, c in enumerate(reranked, 1):
        meta = c["metadata"]
        text = (meta.get("text") or meta.get("chunk_text", ""))[:500]
        print(f"\n--- Chunk {i} ---")
        print(f"Doc: {meta.get('doc_id')} | Chunk: {meta.get('chunk_id')}")
        print(text)


    # 🧠 Build medical-specific prompt
    # This uses the chunks to build the query that will finally go to qwen2.5.
    prompt = build_medical_policy_prompt(reranked, payer, cpt_code)
    print('✓ Built medical policy extraction prompt')
    print("\n🧠 FINAL PROMPT SENT TO MODEL:\n")
    print(prompt)


    # Generate with higher token limit for medical policies
    raw_output = generate_with_context(prompt, max_new_tokens=400) # maybe change back to 800, yah so 256 didn't work :cry_face:, 400 was quicker and gave comproable results.
    print('✓ Generated policy extraction')
    print("\n🤖 RAW MODEL OUTPUT:\n")
    print(raw_output)
    print("\n🔚 END RAW OUTPUT\n")

    if raw_output.count("{") != raw_output.count("}"):
        print("⚠️ Brace mismatch detected — model likely cut off or added text")

    if "Human:" in raw_output or "JSON OUTPUT" in raw_output:
        print("⚠️ Model is continuing conversation instead of stopping at JSON")

    if not raw_output:
        return {
            "rules": {"error": "Generation failed"},
            "context": [],
            "raw_output": ""
        }

    ### Nice and clean debug printer
    # print("\n================ RAG DEBUG ================")
    # print(f"Payer: {payer} | CPT: {cpt_code}")
    # print(f"Retrieved: {len(candidates)} | Reranked: {len(reranked)}")

    # print("\n--- TOP CHUNKS ---")
    # for i, c in enumerate(reranked[:5], 1):
    #     meta = c["metadata"]
    #     text = (meta.get("text") or meta.get("chunk_text", ""))[:300]
    #     print(f"{i}. {meta.get('doc_id')} | {meta.get('chunk_id')}")
    #     print(text, "\n")

    # print("\n--- PROMPT ---\n", prompt[:2000])  # avoid terminal spam

    # print("\n--- RAW OUTPUT ---\n", raw_output)
    # print("===========================================\n")


    # 🧾 Parse JSON safely with fallback
    try:
        # Try to find JSON in the output (in case of extra text)
        json_start = raw_output.find('{')
        json_end = raw_output.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = raw_output[json_start:json_end]
            print("\n✂️ EXTRACTED JSON STRING:\n")
            print(json_str)
            print("\n📏 Length:", len(json_str))
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