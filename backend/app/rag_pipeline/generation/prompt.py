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

    prompt = f"""You are a medical policy analyst. Extract coverage criteria with PRECISE categorization.

CRITICAL CLASSIFICATION RULES:

1. CLINICAL INDICATIONS = Diagnoses/conditions that QUALIFY for coverage
   - Extract from sections titled: "DIAGNOSIS REQUIREMENT", "CLINICAL FINDINGS"
   - These answer: "What medical conditions make a patient eligible?"
   - Example: "Meniscal tear (ICD M23.2xx)", "Positive McMurray's test"
   
2. PREREQUISITES = What must be done BEFORE getting the MRI
   - Conservative treatment requirements (e.g., "6 weeks physical therapy")
   - Prior imaging requirements (e.g., "X-rays within 60 days")
   - These answer: "What must the patient complete first?"
   - DO NOT include repeat imaging criteria here
   
3. EXCLUSION CRITERIA = When coverage is explicitly DENIED
   - Sections titled: "NOT MEDICALLY NECESSARY"
   - These start with phrases like: "MRI is NOT covered for..."
   - Example: "Routine screening without symptoms"
   
4. DOCUMENTATION REQUIREMENTS = Paperwork needed for authorization
   - What must be submitted with the prior auth request
   - Example: "Clinical notes within 30 days", "X-ray report"

5. QUANTITY LIMITS = Timing/frequency restrictions
   - Authorization validity periods
   - Repeat imaging rules (if member already had MRI)
   - Example: "Valid for 60 days", "Repeat within 12 months requires..."

DO NOT MIX CATEGORIES:
- Exclusions go ONLY in exclusion_criteria (not in clinical_indications)
- Repeat imaging rules go in quantity_limits (not in prerequisites)
- Conservative treatment goes in prerequisites (not in clinical_indications)

CONTEXT DOCUMENTS:
{context_text}

Extract for CPT code {cpt_code}.

OUTPUT (valid JSON only, no markdown):
{{
  "payer": "Aetna",
  "cpt_code": "{cpt_code}",
  "coverage_criteria": {{
    "clinical_indications": ["diagnosis/condition 1", "clinical finding 2"],
    "prerequisites": ["completed treatment requirement", "prior imaging requirement"],
    "exclusion_criteria": ["NOT covered scenario 1", "NOT covered scenario 2"],
    "documentation_requirements": ["specific paperwork needed"],
    "quantity_limits": {{
      "authorization_validity": "timeframe",
      "repeat_imaging": "rules for repeat within timeframe"
    }}
  }},
  "source_references": ["chunk_id_1", "chunk_id_2"]
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
