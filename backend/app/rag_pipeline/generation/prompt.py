# generation/prompt.py
from typing import List

# THIS IS NOT USED ATM
# PROMPT_TEMPLATE = """<output_format>JSON only - no explanations</output_format>

# Extract prior authorization rules from the context below.

# Rules:
# - Output valid JSON only
# - No markdown, no explanations
# - Start with {{ and end with }}

# {context}

# JSON OUTPUT:
# """

# def build_prompt(chunks: List[dict]) -> str:
#     """
#     Build the extraction prompt with properly formatted and sanitized context.
#     """
#     ctx_lines = []
    
#     for i, chunk in enumerate(chunks):
#         md = chunk.get('metadata', {})
        
#         # Get text and SANITIZE it
#         text = (
#             md.get('text') or 
#             md.get('chunk_text') or 
#             chunk.get('text') or 
#             chunk.get('page_content') or 
#             ""
#         ).strip()
        
#         # CRITICAL: Remove potential prompt injections
#         # Remove any text that looks like instructions or JSON commands
#         suspicious_patterns = [
#             r'COMMAND FORMAT:',
#             r'BEGIN CONTEXT:',
#             r'Extract the coverage criteria now',
#             r'Return ONLY',
#             r'<critical_instruction>',
#             r'You are extracting',
#         ]
        
#         for pattern in suspicious_patterns:
#             if pattern.lower() in text.lower():
#                 # Log warning
#                 print(f"⚠️ Warning: Suspicious pattern detected in chunk {i}: {pattern}")
#                 # Optionally truncate or skip
        
#         # Build source citation
#         doc_id = md.get('doc_id') or md.get('document_id') or f'doc_{i}'
#         chunk_id = md.get('chunk_id') or md.get('id') or str(i)
#         source = f"[{doc_id}:{chunk_id}]"
        
#         # Format with clear separation
#         if text:
#             # Escape any JSON-like content in the source text
#             text = text.replace('{', '{{').replace('}', '}}')
#             ctx_lines.append(f"Source: {source}\nContent: {text}\n{'-' * 80}")
    
#     context = "\n\n".join(ctx_lines)
    
#     if not context.strip():
#         context = "[No relevant context found]"
    
#     return PROMPT_TEMPLATE.format(context=context)

# generation/prompt.py
# This is building another prompt that utilizes the top ranked chunks to create the structured JSON I need.
def build_medical_policy_prompt(context_chunks: list, payer: str, cpt_code: str) -> str:
    """
    Build a structured prompt for medical policy extraction
    """
    context_text = "\n\n".join([
        f"Source {i+1}: {chunk['metadata'].get('text', chunk['metadata'].get('chunk_text', ''))}"
        for i, chunk in enumerate(context_chunks)
    ])
    
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

JSON OUTPUT:"""
    
    return prompt

# def build_prompt(chunks: List[dict]) -> str:
#     """
#     Build the extraction prompt with properly formatted context.
    
#     Args:
#         chunks: List of retrieved document chunks with metadata
        
#     Returns:
#         Complete prompt string ready for LLM
#     """
#     ctx_lines = []
    
#     for i, chunk in enumerate(chunks):
#         md = chunk.get('metadata', {})
        
#         # Get text from various possible fields
#         text = (
#             md.get('text') or 
#             md.get('chunk_text') or 
#             chunk.get('text') or 
#             chunk.get('page_content') or 
#             ""
#         ).strip()
        
#         # Build source citation
#         doc_id = md.get('doc_id') or md.get('document_id') or 'unknown'
#         chunk_id = md.get('chunk_id') or md.get('id') or str(i)
#         source = f"[{doc_id}:{chunk_id}]"
        
#         # Format with clear separation
#         if text:
#             ctx_lines.append(f"Source: {source}\nContent: {text}\n{'-' * 80}")
    
#     context = "\n\n".join(ctx_lines)
    
#     # Handle empty context
#     if not context.strip():
#         context = "[No relevant context found]"
    
#     return PROMPT_TEMPLATE.format(context=context)

# # Entertain this function here later.
# def validate_extraction(result: dict) -> List[str]:
#     """Validate extracted rules for common issues."""
#     errors = []
    
#     if not result.get('rules'):
#         return errors
    
#     for rule in result['rules']:
#         # Check required fields
#         required = ['id', 'field', 'operator', 'source']
#         missing = [f for f in required if f not in rule]
#         if missing:
#             errors.append(f"Rule {rule.get('id', '?')} missing: {missing}")
        
#         # Validate operator-value compatibility
#         if rule.get('operator') in ['>=', '<=', '>', '<']:
#             if not isinstance(rule.get('value'), (int, float)):
#                 errors.append(f"Rule {rule['id']}: numeric operator requires numeric value")
        
#         # Check source format
#         source = rule.get('source', '')
#         if not source.startswith('[') or ':' not in source:
#             errors.append(f"Rule {rule['id']}: invalid source format")
    
#     return errors