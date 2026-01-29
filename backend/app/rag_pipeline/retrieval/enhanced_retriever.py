"""
Enhanced retrieval functions that leverage the rich metadata from improved_chunker.

This module provides metadata-aware retrieval that boosts relevant chunks
based on query intent and structural information.
"""

import re
from typing import List, Dict, Tuple


def extract_codes_from_query(query: str) -> Tuple[List[str], List[str]]:
    """
    Extract CPT and ICD-10 codes from query text.
    
    Returns:
        (cpt_codes, icd_codes)
    """
    # CPT codes: 5 digits
    cpt_codes = re.findall(r'\b\d{5}\b', query)
    
    # ICD-10 codes: Letter followed by digits, possibly with dots/x
    icd_codes = re.findall(r'\b[A-Z]\d{2}\.?[\dxX]+\b', query)
    
    return cpt_codes, icd_codes


def analyze_query_intent(query: str) -> Dict[str, bool]:
    """
    Analyze query to understand user intent.
    
    Returns dict with intent flags:
        - is_exception_query: Looking for ways to bypass requirements
        - is_requirement_query: Asking what's required
        - is_definition_query: Asking for clarification/definitions
        - mentions_codes: Contains CPT/ICD codes
    """
    query_lower = query.lower()
    
    # Exception indicators
    exception_words = [
        'without', 'skip', "don't need", "don't have to", 
        'bypass', 'waive', 'exception', 'not required',
        'instead of', 'alternative to'
    ]
    is_exception_query = any(word in query_lower for word in exception_words)
    
    # Requirement indicators
    requirement_words = [
        'require', 'need', 'must', 'necessary', 'mandatory',
        'have to', 'criteria', 'qualification'
    ]
    is_requirement_query = any(word in query_lower for word in requirement_words)
    
    # Definition indicators
    definition_words = [
        'what is', 'define', 'definition', 'mean', 'clarify',
        'explain', 'how long', 'how many'
    ]
    is_definition_query = any(word in query_lower for word in definition_words)
    
    # Check for codes
    cpt_codes, icd_codes = extract_codes_from_query(query)
    mentions_codes = bool(cpt_codes or icd_codes)
    
    return {
        'is_exception_query': is_exception_query,
        'is_requirement_query': is_requirement_query,
        'is_definition_query': is_definition_query,
        'mentions_codes': mentions_codes,
        'cpt_codes': cpt_codes,
        'icd_codes': icd_codes,
    }


def retrieve_with_metadata_boost(
    query: str,
    store,
    embedder,
    top_k: int = 20,
    final_k: int = 5
) -> List[Dict]:
    """
    Enhanced retrieval that uses metadata to boost relevant chunks.
    
    Args:
        query: User query
        store: FAISS vector store
        embedder: Embedding model
        top_k: Number of chunks to retrieve initially
        final_k: Number of chunks to return after boosting
    
    Returns:
        List of top chunks with metadata
    """
    # Get query intent
    intent = analyze_query_intent(query)
    
    # Embed query and search
    query_vector = embedder.embed([query])[0]
    results = store.search(query_vector, k=top_k)
    
    # Apply metadata-based boosts
    boosted_results = []
    
    for score, metadata in results:
        boost_factor = 1.0
        boost_reasons = []
        
        # 1. Exception query boost
        if intent['is_exception_query'] and metadata.get('is_exception'):
            boost_factor *= 1.5
            boost_reasons.append("exception_match")
        
        # 2. Requirement query boost
        if intent['is_requirement_query'] and metadata.get('is_requirement'):
            boost_factor *= 1.3
            boost_reasons.append("requirement_match")
        
        # 3. Definition query boost
        if intent['is_definition_query'] and metadata.get('is_definition'):
            boost_factor *= 1.3
            boost_reasons.append("definition_match")
        
        # 4. Code matching (strong boost)
        chunk_codes = metadata.get('cpt_codes', []) + metadata.get('icd_codes', [])
        if intent['mentions_codes']:
            mentioned_codes = intent['cpt_codes'] + intent['icd_codes']
            if any(code in chunk_codes for code in mentioned_codes):
                boost_factor *= 2.0
                boost_reasons.append("exact_code_match")
        
        # 5. Logical operator alignment
        if 'all' in query.lower() and metadata.get('logical_operator') == 'ALL':
            boost_factor *= 1.2
            boost_reasons.append("all_criteria_match")
        elif 'one' in query.lower() and metadata.get('logical_operator') == 'ONE':
            boost_factor *= 1.2
            boost_reasons.append("one_criteria_match")
        
        # 6. Rule type relevance
        query_lower = query.lower()
        rule_type = metadata.get('rule_type', '')
        
        if 'diagnosis' in query_lower and 'diagnosis' in rule_type:
            boost_factor *= 1.3
            boost_reasons.append("rule_type_match")
        elif 'treatment' in query_lower and 'treatment' in rule_type:
            boost_factor *= 1.3
            boost_reasons.append("rule_type_match")
        elif 'imaging' in query_lower and 'imaging' in rule_type:
            boost_factor *= 1.3
            boost_reasons.append("rule_type_match")
        elif ('age' in query_lower or 'elderly' in query_lower or 'old' in query_lower) and 'age' in rule_type:
            boost_factor *= 1.4
            boost_reasons.append("rule_type_match")
        
        # Apply boost
        boosted_score = score * boost_factor
        
        # Add boost info to metadata for debugging
        metadata['boost_factor'] = boost_factor
        metadata['boost_reasons'] = boost_reasons
        metadata['original_score'] = score
        metadata['boosted_score'] = boosted_score
        
        boosted_results.append((boosted_score, metadata))
    
    # Sort by boosted score
    boosted_results.sort(key=lambda x: x[0], reverse=True)
    
    # Return top final_k
    return [metadata for _, metadata in boosted_results[:final_k]]


def format_chunk_for_llm(chunk: Dict, include_metadata: bool = True) -> str:
    """
    Format a chunk for presentation to the LLM.
    
    Args:
        chunk: Chunk metadata dict
        include_metadata: Whether to include structural metadata
    
    Returns:
        Formatted string for LLM context
    """
    parts = []
    
    # Add section context
    if chunk.get('parent_context') and chunk.get('parent_context') != chunk.get('section_header'):
        parts.append(f"[Parent Section: {chunk['parent_context']}]")
    
    parts.append(f"[Section: {chunk.get('section_header', 'N/A')}]")
    
    # Add important metadata flags
    if include_metadata:
        flags = []
        
        if chunk.get('is_exception'):
            flags.append("⚡ EXCEPTION CLAUSE")
        
        if chunk.get('is_requirement'):
            flags.append("✓ REQUIREMENT")
        
        if chunk.get('logical_operator'):
            op = chunk['logical_operator']
            flags.append(f"⚠️ Requires {op} of the following criteria")
        
        if flags:
            parts.append(" | ".join(flags))
    
    # Add the main text
    parts.append("")
    parts.append(chunk['text'])
    
    # Add codes if present
    if chunk.get('cpt_codes') or chunk.get('icd_codes'):
        code_parts = []
        if chunk.get('cpt_codes'):
            code_parts.append(f"CPT: {', '.join(chunk['cpt_codes'])}")
        if chunk.get('icd_codes'):
            code_parts.append(f"ICD-10: {', '.join(chunk['icd_codes'])}")
        parts.append("")
        parts.append(f"[Relevant Codes: {' | '.join(code_parts)}]")
    
    return "\n".join(parts)


def retrieve_and_format(
    query: str,
    store,
    embedder,
    top_k: int = 5,
    include_metadata: bool = True,
    verbose: bool = False
) -> str:
    """
    Complete retrieval pipeline: retrieve chunks and format for LLM.
    
    Args:
        query: User query
        store: FAISS vector store
        embedder: Embedding model
        top_k: Number of chunks to retrieve
        include_metadata: Include structural metadata in output
        verbose: Print debug info
    
    Returns:
        Formatted context string for LLM
    """
    # Retrieve with metadata boosting
    chunks = retrieve_with_metadata_boost(
        query=query,
        store=store,
        embedder=embedder,
        top_k=20,  # Retrieve more initially
        final_k=top_k  # Return fewer after boosting
    )
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        print(f"\nRetrieved {len(chunks)} chunks:\n")
        
        for i, chunk in enumerate(chunks, 1):
            print(f"{i}. {chunk.get('section_header', 'N/A')}")
            print(f"   Rule Type: {chunk.get('rule_type', 'N/A')}")
            print(f"   Original Score: {chunk.get('original_score', 0):.4f}")
            print(f"   Boost Factor: {chunk.get('boost_factor', 1.0):.2f}x")
            print(f"   Boosted Score: {chunk.get('boosted_score', 0):.4f}")
            if chunk.get('boost_reasons'):
                print(f"   Boost Reasons: {', '.join(chunk['boost_reasons'])}")
            print()
    
    # Format chunks for LLM
    formatted_chunks = [
        format_chunk_for_llm(chunk, include_metadata=include_metadata)
        for chunk in chunks
    ]
    
    # Combine with separators
    context = "\n\n" + "="*80 + "\n\n"
    context += "\n\n---\n\n".join(formatted_chunks)
    
    return context


# Example usage
if __name__ == "__main__":
    # This would normally be called from your main retrieval pipeline
    
    from backend.app.rag_pipeline.build_index import STORE, EMBEDDER, load_index
    
    # Load the index
    load_index("mocked_insurance_policy")
    
    # Test queries
    test_queries = [
        "Do I need physical therapy before knee MRI?",
        "I tore my ACL, do I still need 6 weeks of treatment?",
        "What ICD-10 codes qualify for knee MRI?",
        "Can athletes get expedited approval?",
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"TESTING QUERY: {query}")
        print(f"{'='*80}\n")
        
        context = retrieve_and_format(
            query=query,
            store=STORE,
            embedder=EMBEDDER,
            top_k=3,
            verbose=True
        )
        
        print("\nFormatted Context for LLM:")
        print(context)
        print("\n")