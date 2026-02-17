import json
import logging
import app.rag_pipeline.scripts.build_index_updated as build_index
from app.rag_pipeline.retrieval.enhanced_reranker import Reranker
from app.rag_pipeline.retrieval.enhanced_retriever import retrieve_and_format
from app.rag_pipeline.generation.prompt import build_medical_policy_prompt
from app.rag_pipeline.generation.generator import generate_with_context

logger = logging.getLogger(__name__)

# Default PT duration requirement per Aetna policy (weeks)
# Used when PT is mentioned in the policy but no duration is explicitly stated
DEFAULT_PT_DURATION_WEEKS = 6


def _validate_policy_consistency(rules: list) -> bool:
    """
    Validate that extracted policy rules are internally consistent.

    Specifically ensures the PT requirement rule always contains BOTH:
    - pt_attempted == True (was PT performed?)
    - pt_duration_weeks >= N (for how long?)

    Without both conditions, the rule is ambiguous and will produce
    inconsistent evaluation results across LLM extraction runs.

    Returns True if consistent, False if corrections were made.
    Modifies the rules list in-place.

    Priority: P2 - MEDIUM (Issue 5: Inconsistent PT Requirements)
    Root cause: LLM extraction sometimes omits duration from policy text,
    causing normalize_policy_criteria() to generate an incomplete PT rule.
    """
    pt_rule = next((r for r in rules if r.get("id") == "physical_therapy_requirement"), None)

    if not pt_rule:
        # PT rule not present — nothing to validate
        return True

    conditions = pt_rule.get("conditions", [])
    has_attempted_check = any(c.get("field") == "pt_attempted" for c in conditions)
    has_duration_check = any(c.get("field") == "pt_duration_weeks" for c in conditions)

    if has_attempted_check and has_duration_check:
        # Rule is complete — no correction needed
        return True

    # Rule is incomplete — log and correct
    if not has_attempted_check:
        logger.warning(
            "PT rule missing 'pt_attempted' condition. Adding default check."
        )
        conditions.append({
            "field": "pt_attempted",
            "operator": "eq",
            "value": True
        })

    if not has_duration_check:
        logger.warning(
            f"PT rule missing 'pt_duration_weeks' condition. "
            f"Adding default: >= {DEFAULT_PT_DURATION_WEEKS} weeks. "
            f"Root cause: Policy extraction did not include PT duration. "
            f"Using standard Aetna requirement of {DEFAULT_PT_DURATION_WEEKS} weeks."
        )
        conditions.append({
            "field": "pt_duration_weeks",
            "operator": "gte",
            "value": DEFAULT_PT_DURATION_WEEKS
        })
        # Update description to reflect the corrected rule
        pt_rule["description"] = (
            f"Physical therapy must be attempted and documented "
            f"(minimum {DEFAULT_PT_DURATION_WEEKS} weeks) "
            f"[duration defaulted — not found in extracted policy text]"
        )

    pt_rule["conditions"] = conditions
    return False


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

    # query = f"""
    #     {payer} CPT code {cpt_code} knee MRI medical necessity criteria including:
    #     diagnosis requirements, clinical findings, examination tests,
    #     conservative treatment, imaging requirements, documentation,
    #     authorization validity, and coverage exclusions"""
    
    #     query = """
    # Aetna policy CPT 73721 knee MRI:
    # - Diagnosis requirements and ICD codes
    # - Clinical examination findings (McMurray, Thessaly, Lachman tests)
    # - Conservative treatment duration requirements
    # - Prior imaging requirements (X-rays)
    # - Documentation needed for authorization
    # - Coverage exclusions and non-covered scenarios
    # """

    # Or be even more explicit:
    query = f"{payer} CPT {cpt_code} medical necessity criteria: diagnosis codes, clinical findings, conservative treatment requirements, imaging prerequisites, authorization documentation"    


    # Retrieve candidates/context
    context = retrieve_and_format(
        query=query,
        store= build_index.STORE,
        embedder=build_index.EMBEDDER,
        top_k=12,
        verbose=True
    )
    # retriever = Retriever(build_index.EMBEDDER, build_index.STORE, top_k=40)
    # candidates = retriever.retrieve(query)
    print(f'✓ Retrieved {len(context)} candidate chunks')
    print("\nDEBUG TYPE CHECK:")
    print("Type of context:", type(context))
    print("First element type:", type(context[0]) if isinstance(context, list) else "N/A")
    # print("Preview:", repr(context[:200]))

    if not context:
        return {
            "rules": {"error": "No relevant policy documents found"},
            "context": [],
            "raw_output": ""
        }

    # Rerank 
    # With the specialized retrieved chunks I then rerank to get my top chunks.
    reranker = Reranker()
    reranked = reranker.rerank(query, context, top_k=6, verbose=True)
    # print(f'✓ Reranked to top {len(reranked)} chunks')
    # print("\n📚 TOP RERANKED CHUNKS SENT TO LLM:\n")

    # 🧠 Build medical-specific prompt
    # This uses the chunks to build the query that will finally go to qwen2.5.

    # prompt = build_medical_policy_prompt(context, payer, cpt_code) # trying with just the first retrieved chunks.
    prompt = build_medical_policy_prompt(reranked, payer, cpt_code) # reranked line
    print('✓ Built medical policy extraction prompt')
    print("\n🧠 FINAL PROMPT SENT TO MODEL:\n")
    print(prompt)


    # Generate with higher token limit for medical policies
    # raw_output = generate_with_context(prompt, max_tokens=400, provider="local") # maybe change back to 800, yah so 256 didn't work :cry_face:, 400 was quicker and gave comproable results.
    raw_output = generate_with_context(
            prompt, 
            provider="groq",
            model_name="llama-3.3-70b-versatile",
            max_tokens= 2048
        )
    
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
    context_chunks = []

    for c in reranked:
        meta = c.get("metadata", c)  # fallback to flat structure

        doc_id = (
            meta.get("doc_id")
            or meta.get("doc_name")
            or "unknown_doc"
        )

        chunk_id = meta.get("chunk_id", "?")

        text = (
            meta.get("text")
            or meta.get("chunk_text")
            or ""
        )

        preview = text[:300].replace("\n", " ").strip()

        context_chunks.append(f"[{doc_id}:{chunk_id}] {preview}...")

    return {
        "rules": rules_json,
        "context": context_chunks,  # Now list of strings
        "raw_output": raw_output
    }


# if __name__ == "__main__":
#     result = extract_policy_rules("Aetna", "73721")
    
#     print("\n" + "="*60)
#     print("EXTRACTED POLICY RULES")
#     print("="*60)
#     print(json.dumps(result["rules"], indent=2))
    
#     print("\n" + "="*60)
#     print("SOURCE CONTEXT")
#     print("="*60)
#     for i, ctx in enumerate(result["context"][:3]):
#         print(f"\n[{i+1}] {ctx}")
