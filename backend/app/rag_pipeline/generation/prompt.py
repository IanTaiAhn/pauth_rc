# generation/prompt.py
from typing import List
# from backend.app.rag_pipeline.retrieval.enhanced_retriever import format_chunk_for_llm



def build_medical_policy_prompt(context_chunks: list, payer: str, cpt_code: str) -> str:
    """
    Build a structured prompt for medical policy extraction
    Works with BOTH wrapped {"metadata": {...}} and raw chunk dicts.
    """

    formatted_sources = []

    for i, chunk in enumerate(context_chunks):
        # Handle both formats
        meta = chunk.get("metadata", chunk)

        text = meta.get("text") or meta.get("chunk_text") or ""
        doc = meta.get("doc_name", "unknown_doc")
        chunk_id = meta.get("chunk_id", f"chunk_{i+1}")

        formatted_sources.append(
            f"Source {i+1} (Doc: {doc} | ID: {chunk_id}):\n{text}"
        )

    context_text = "\n\n".join(formatted_sources)

    prompt = f"""You are a medical policy analyst extracting coverage criteria from insurance documents.

CRITICAL INSTRUCTIONS:
1. Extract COMPLETE lists - if text says "ALL of the following criteria are met:", 
   you MUST find what those criteria are in the context (may be in a different source)
2. Look for EXCEPTIONS clauses - if text says "EXCEPTIONS to [requirement]:", 
   extract those as separate items or note them
3. Extract ALL timing/quantity restrictions:
   - Authorization validity periods
   - Repeat imaging requirements  
   - Time windows for documentation
4. If a field's header appears but content is incomplete, note "See additional criteria in source"

CONTEXT DOCUMENTS:
{context_text}

EXTRACTION RULES:
- For "prerequisites": Extract ALL treatment requirements including duration/quantity details
- For "clinical_indications": Extract the specific conditions that qualify for coverage
- For "exclusion_criteria": Extract situations where MRI is NOT covered
- For "documentation_requirements": Extract what must be submitted with auth request
- For "quantity_limits": Extract any timing restrictions (e.g., "within 60 days", "12 months")

EXAMPLE:
If source says: "when ALL of the following criteria are met:" but doesn't list them,
AND another source lists diagnosis requirements,
THEN extract from the second source as clinical_indications.

If source says: "EXCEPTIONS to conservative treatment requirement: [list]"
THEN add these to prerequisites with prefix "EXCEPTIONS: [list]"

Extract as:
"prerequisites": [
  "Completed at least 6 weeks (42 days) of conservative therapy, including at least TWO of the following: (1) Physical therapy (minimum 6 sessions documented), (2) NSAIDs or analgesics (trial of at least 4 weeks), (3) Activity modification and home exercise program, (4) Bracing or orthotics"
]

TASK:
Extract ALL medical necessity criteria for Aetna's coverage of CPT code 73721.

OUTPUT FORMAT (valid JSON only, no markdown):
{{
  "payer": "Aetna",
  "cpt_code": "73721",
  "coverage_criteria": {{
    "clinical_indications": ["specific condition 1", "specific condition 2"],
    "prerequisites": ["complete requirement with details"],
    "exclusion_criteria": ["NOT covered scenario 1", "NOT covered scenario 2"],
    "documentation_requirements": ["specific doc requirement with timeframe"],
    "quantity_limits": {{"type": "description with timeframe"}}
  }},
  "source_references": ["general_main", "prior_imaging_main", "conservative_treatment_main"]
}}
"""

    return prompt


# Prompt here wasn't bad tbh

# def build_medical_policy_prompt(context_chunks: list, payer: str, cpt_code: str) -> str:
#     """
#     Build a structured prompt for medical policy extraction
#     """
#     context_text = "\n\n".join([
#         f"Source {i+1}: {chunk['metadata'].get('text', chunk['metadata'].get('chunk_text', ''))}"
#         for i, chunk in enumerate(context_chunks)
#     ])
    
#     prompt = f"""You are a medical policy analyst extracting coverage criteria from insurance documents.

# CONTEXT DOCUMENTS:
# {context_text}

# TASK:
# Extract the medical necessity criteria for {payer}'s coverage of CPT code {cpt_code}.

# OUTPUT FORMAT (JSON only, no additional text):
# {{
#   "payer": "{payer}",
#   "cpt_code": "{cpt_code}",
#   "coverage_criteria": {{
#     "clinical_indications": ["list of approved diagnoses/conditions"],
#     "prerequisites": ["required prior treatments or tests"],
#     "exclusion_criteria": ["conditions where NOT covered"],
#     "documentation_requirements": ["required medical documentation"],
#     "quantity_limits": {{"description": "frequency/quantity limits if any"}}
#   }},
#   "source_references": ["document IDs used"]
# }}

# JSON OUTPUT:"""
    
#     return prompt
