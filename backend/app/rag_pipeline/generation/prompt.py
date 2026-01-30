# generation/prompt.py
from typing import List
from backend.app.rag_pipeline.retrieval.enhanced_retriever import format_chunk_for_llm

# Format for format_chunk_for_llm
# def build_medical_policy_prompt(context_chunks: list, payer: str, cpt_code: str) -> str:
#     """
#     Build a structured prompt for medical policy extraction
#     """

#     formatted_chunks = [
#         format_chunk_for_llm(chunk, include_metadata=True)
#         for chunk in context_chunks
#     ]

#     context_text = "\n\n" + "="*80 + "\n\n"
#     context_text += "\n\n---\n\n".join(formatted_chunks)

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

CONTEXT DOCUMENTS:
{context_text}

TASK:
Extract the medical necessity criteria for {payer}'s coverage of CPT code {cpt_code}.

OUTPUT FORMAT (JSON only, no additional text):
{{
  "payer": "{payer}",
  "cpt_code": "{cpt_code}",
  "coverage_criteria": {{
    "clinical_indications": ["list of approved diagnoses/conditions"],
    "prerequisites": ["required prior treatments or tests"],
    "exclusion_criteria": ["conditions where NOT covered"],
    "documentation_requirements": ["required medical documentation"],
    "quantity_limits": {{"description": "frequency/quantity limits if any"}}
  }},
  "source_references": ["document IDs used"]
}}
"""

    return prompt


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
