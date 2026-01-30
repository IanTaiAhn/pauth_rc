"""
Enhanced Reranker for Insurance Policy Documents

This reranker leverages the rich metadata from the improved chunker to make
intelligent reranking decisions based on:
- Rule types and their importance
- Logical operators (ALL, ONE, TWO)
- Exception vs requirement flags
- Code relevance
- Query intent alignment
"""

from pathlib import Path
from sentence_transformers import CrossEncoder
import re
from typing import List, Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = BASE_DIR / "models" / "minilm_reranker"


# Rule-type importance weights (UPDATED with new types)
RULE_TYPE_WEIGHTS = {
    # High priority - these directly determine approval
    "coverage_criteria": 1.4,
    "diagnosis_requirement": 1.3,
    "clinical_findings": 1.25,
    "conservative_treatment": 1.3,
    "imaging_requirement": 1.2,
    "exceptions": 1.35,  # BOOSTED - exceptions are critical
    
    # Medium priority - important context
    "age_rules": 1.1,
    "prior_imaging": 1.1,
    "special_populations": 1.15,
    "pa_requirements": 1.2,
    
    # Lower priority - supporting info
    "documentation": 0.8,
    "exclusions": 0.9,
    "not_medically_necessary": 0.7,
    "faq": 0.85,
    
    # Administrative/context
    "admin": 0.5,
    "appendix": 0.4,
    "policy_statement": 0.6,
    "general": 0.7
}


# Criteria keywords for detecting important language
CRITERIA_KEYWORDS = {
    # Requirements
    "must": 0.05,
    "required": 0.05,
    "medically necessary": 0.06,
    "shall": 0.04,
    "mandatory": 0.05,
    
    # Logical operators
    "all of the following": 0.07,
    "at least one": 0.06,
    "at least two": 0.06,
    "any of the following": 0.05,
    
    # Quantitative criteria
    "within": 0.04,
    "minimum": 0.04,
    "at least": 0.05,
    "no less than": 0.04,
    "no more than": 0.04,
    
    # Documentation/completion
    "documented": 0.04,
    "completed": 0.04,
    "prior to": 0.04,
    
    # Exceptions (very important!)
    "exception": 0.08,
    "not required": 0.07,
    "bypass": 0.06,
    "waive": 0.06,
}


class Reranker:
    """
    Enhanced reranker that uses both CrossEncoder scores and metadata-based boosting.
    """
    
    def __init__(self, model_path: str = None):
        """
        Initialize reranker with CrossEncoder model.
        
        Args:
            model_path: Path to CrossEncoder model. If None, uses default.
        """
        if model_path is None:
            model_path = str(DEFAULT_MODEL_DIR)
        
        try:
            self.model = CrossEncoder(str(model_path))
            self.has_model = True
        except Exception as e:
            print(f"Warning: Could not load CrossEncoder model: {e}")
            print("Falling back to metadata-only reranking")
            self.model = None
            self.has_model = False
    
    def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyze query to understand what the user is looking for.
        This helps boost relevant chunks.
        """
        query_lower = query.lower()
        
        return {
            # Looking for ways to bypass requirements
            'seeks_exception': any(word in query_lower for word in [
                'without', 'skip', "don't need", 'bypass', 'waive', 'exception'
            ]),
            
            # Asking what's required
            'seeks_requirement': any(word in query_lower for word in [
                'require', 'need', 'must', 'necessary', 'criteria', 'qualify'
            ]),
            
            # Asking for clarification/definitions
            'seeks_definition': any(word in query_lower for word in [
                'what is', 'define', 'mean', 'clarify', 'explain'
            ]),
            
            # Mentions specific codes
            'mentions_codes': bool(re.search(r'\b([A-Z]\d{2}\.?[\dxX]+|\d{5})\b', query)),
            
            # Asking about specific populations
            'mentions_age': any(word in query_lower for word in [
                'age', 'elderly', 'senior', 'pediatric', 'child', 'young', 'old'
            ]),
            
            # Asking about all requirements (comprehensive)
            'seeks_comprehensive': any(phrase in query_lower for phrase in [
                'all requirement', 'all criteria', 'everything', 'complete list'
            ]),
        }
    
    def extract_codes_from_query(self, query: str) -> Tuple[List[str], List[str]]:
        """Extract CPT and ICD codes from query"""
        cpt_codes = re.findall(r'\b\d{5}\b', query)
        icd_codes = re.findall(r'\b[A-Z]\d{2}\.?[\dxX]+\b', query)
        return cpt_codes, icd_codes
    
    def keyword_boost(self, text: str) -> float:
        """
        Calculate boost based on criteria keywords in text.
        
        Returns boost multiplier (e.g., 1.15 means 15% boost)
        """
        text_lower = text.lower()
        boost = 1.0
        
        for keyword, boost_value in CRITERIA_KEYWORDS.items():
            if keyword in text_lower:
                boost += boost_value
        
        # Cap total keyword boost
        return min(boost, 1.25)
    
    def metadata_boost(self, candidate: Dict, query_intent: Dict, 
                       query_codes: Tuple[List[str], List[str]]) -> float:
        """
        Calculate boost based on metadata alignment with query intent.
        
        This is the key enhancement - using the improved chunker's metadata!
        """
        metadata = candidate.get("metadata", {})
        boost = 1.0
        boost_reasons = []
        
        # 1. EXCEPTION ALIGNMENT
        if query_intent['seeks_exception'] and metadata.get('is_exception'):
            boost *= 1.5
            boost_reasons.append("exception_match")
        
        # Demote requirements if user is asking about exceptions
        elif query_intent['seeks_exception'] and metadata.get('is_requirement'):
            boost *= 0.7
            boost_reasons.append("requirement_when_seeking_exception")
        
        # 2. REQUIREMENT ALIGNMENT
        if query_intent['seeks_requirement'] and metadata.get('is_requirement'):
            boost *= 1.3
            boost_reasons.append("requirement_match")
        
        # 3. DEFINITION ALIGNMENT
        if query_intent['seeks_definition'] and metadata.get('is_definition'):
            boost *= 1.25
            boost_reasons.append("definition_match")
        
        # 4. CODE MATCHING (very strong signal)
        cpt_mentioned, icd_mentioned = query_codes
        chunk_cpts = metadata.get('cpt_codes', [])
        chunk_icds = metadata.get('icd_codes', [])
        
        if cpt_mentioned and any(code in chunk_cpts for code in cpt_mentioned):
            boost *= 2.0
            boost_reasons.append("exact_cpt_match")
        
        if icd_mentioned and self._code_matches(icd_mentioned, chunk_icds):
            boost *= 2.0
            boost_reasons.append("exact_icd_match")
        
        # 5. LOGICAL OPERATOR RELEVANCE
        logical_op = metadata.get('logical_operator')
        if logical_op:
            # If query asks about "all requirements", boost ALL operator chunks
            if query_intent['seeks_comprehensive'] and logical_op == 'ALL':
                boost *= 1.2
                boost_reasons.append("comprehensive_all_match")
            
            # General boost for having logical operator (means it's structured)
            boost *= 1.1
            boost_reasons.append("has_logical_operator")
        
        # 6. PARENT CONTEXT BOOST
        # Chunks with parent context are more complete
        if metadata.get('parent_context'):
            boost *= 1.1
            boost_reasons.append("has_parent_context")
        
        # 7. AGE-RELATED BOOST
        if query_intent['mentions_age'] and 'age' in metadata.get('rule_type', ''):
            boost *= 1.4
            boost_reasons.append("age_match")
        
        # Store boost reasons for debugging
        metadata['rerank_boost_reasons'] = boost_reasons
        
        return boost
    
    def _code_matches(self, query_codes: List[str], chunk_codes: List[str]) -> bool:
        """
        Check if query codes match chunk codes.
        Handles wildcard patterns like M23.2xx
        """
        for chunk_code in chunk_codes:
            # Convert wildcard to regex
            pattern = chunk_code.replace('x', '[0-9A-Z]').replace('X', '[0-9A-Z]')
            pattern = '^' + pattern + '$'
            
            for query_code in query_codes:
                if re.match(pattern, query_code):
                    return True
        return False
    
    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5, 
               verbose: bool = False) -> List[Dict]:
        """
        Rerank candidates using CrossEncoder scores + metadata boosting.
        
        Args:
            query: User query
            candidates: List of candidate chunks (from retrieval)
            top_k: Number of top results to return
            verbose: Print detailed scoring info
        
        Returns:
            Reranked list of candidates
        """
        if not candidates:
            return []
        
        # Normalize candidate format
        candidates = self._normalize_candidates(candidates)
        
        # Analyze query intent
        query_intent = self.analyze_query_intent(query)
        query_codes = self.extract_codes_from_query(query)
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"RERANKING: {len(candidates)} candidates")
            print(f"Query: {query}")
            print(f"Intent: {query_intent}")
            print(f"Codes: CPT={query_codes[0]}, ICD={query_codes[1]}")
            print(f"{'='*80}\n")
        
        # Get CrossEncoder scores if model available
        if self.has_model:
            # Extract text for CrossEncoder
            pairs = []
            for c in candidates:
                text = c.get("metadata", {}).get("text", "")
                if not text:
                    # Fallback if text is missing
                    text = str(c.get("metadata", {}))
                pairs.append((query, text))
            
            base_scores = self.model.predict(pairs)
        else:
            # Fallback: use retrieval scores or uniform scores
            base_scores = [c.get("score", 1.0) for c in candidates]
        
        # Apply all boosting factors
        adjusted = []
        for i, (candidate, base_score) in enumerate(zip(candidates, base_scores)):
            metadata = candidate.get("metadata", {})
            text = metadata.get("text", "")
            rule_type = metadata.get("rule_type", "general")
            
            # Factor 1: Rule type importance
            type_weight = RULE_TYPE_WEIGHTS.get(rule_type, 1.0)
            
            # Factor 2: Criteria keywords
            kw_boost = self.keyword_boost(text)
            
            # Factor 3: Metadata alignment (NEW!)
            meta_boost = self.metadata_boost(candidate, query_intent, query_codes)
            
            # Combine all factors
            final_score = base_score * type_weight * kw_boost * meta_boost
            
            # Store scoring details
            candidate['rerank_score'] = final_score
            candidate['rerank_details'] = {
                'base_score': float(base_score),
                'type_weight': type_weight,
                'keyword_boost': kw_boost,
                'metadata_boost': meta_boost,
                'final_score': final_score
            }
            
            adjusted.append((candidate, final_score))
        
        # Sort by final score
        ranked = sorted(adjusted, key=lambda x: x[1], reverse=True)
        
        if verbose:
            print("\nTop candidates after reranking:\n")
            for i, (cand, score) in enumerate(ranked[:top_k], 1):
                meta = cand.get("metadata", {})
                details = cand.get("rerank_details", {})
                
                print(f"{i}. Score: {score:.4f}")
                print(f"   Section: {meta.get('section_header', 'N/A')}")
                print(f"   Rule Type: {meta.get('rule_type', 'N/A')}")
                print(f"   Breakdown:")
                print(f"      Base: {details.get('base_score', 0):.4f}")
                print(f"      Type: {details.get('type_weight', 1.0):.2f}x")
                print(f"      Keywords: {details.get('keyword_boost', 1.0):.2f}x")
                print(f"      Metadata: {details.get('metadata_boost', 1.0):.2f}x")
                
                if meta.get('rerank_boost_reasons'):
                    print(f"   Boost Reasons: {', '.join(meta['rerank_boost_reasons'])}")
                
                print()
        
        return [r[0] for r in ranked[:top_k]]
    
    def _normalize_candidates(self, candidates: List) -> List[Dict]:
        """
        Normalize candidates to expected format: [{"metadata": {...}, "score": ...}, ...]
        Handles different input formats gracefully.
        """
        normalized = []
        
        for c in candidates:
            # Case 1: Already in correct format
            if isinstance(c, dict) and "metadata" in c:
                normalized.append(c)
            
            # Case 2: Candidate is just the metadata dict itself
            elif isinstance(c, dict):
                # Wrap it in the expected format
                normalized.append({
                    "metadata": c,
                    "score": c.get("boosted_score", c.get("score", 1.0))
                })
            
            # Case 3: Candidate is a string (shouldn't happen, but defensive)
            elif isinstance(c, str):
                normalized.append({
                    "metadata": {"text": c},
                    "score": 1.0
                })
        
        return normalized
    
    def rerank_for_criteria_extraction(self, query: str, candidates: List[Dict], 
                                        top_k: int = 10) -> List[Dict]:
        """
        Specialized reranking for criteria extraction.
        Prioritizes requirements and exceptions over other content.
        
        Use this when extracting criteria for automated evaluation.
        """
        if not candidates:
            return []
        
        # Normalize candidate format
        candidates = self._normalize_candidates(candidates)
        
        # Filter to only requirement/exception chunks
        criteria_chunks = [
            c for c in candidates
            if c.get("metadata", {}).get("is_requirement") or 
               c.get("metadata", {}).get("is_exception")
        ]
        
        # If we filtered out everything, fall back to regular reranking
        if not criteria_chunks:
            return self.rerank(query, candidates, top_k)
        
        # Rerank the criteria chunks
        # For criteria extraction, we want comprehensive coverage
        # So boost exceptions highest, then requirements
        scored = []
        for chunk in criteria_chunks:
            meta = chunk.get("metadata", {})
            
            # Base score
            score = 1.0
            
            # Exception chunks are critical
            if meta.get("is_exception"):
                score *= 2.0
            
            # Requirement chunks are important
            elif meta.get("is_requirement"):
                score *= 1.5
            
            # Boost by rule type importance
            rule_type = meta.get("rule_type", "general")
            score *= RULE_TYPE_WEIGHTS.get(rule_type, 1.0)
            
            # Boost chunks with logical operators (they're well-structured)
            if meta.get("logical_operator"):
                score *= 1.3
            
            # Boost chunks with codes (they're specific)
            if meta.get("cpt_codes") or meta.get("icd_codes"):
                score *= 1.2
            
            scored.append((chunk, score))
        
        # Sort by score
        ranked = sorted(scored, key=lambda x: x[1], reverse=True)
        
        return [r[0] for r in ranked[:top_k]]


# Example usage
if __name__ == "__main__":
    # Mock candidates for testing
    mock_candidates = [
        {
            "metadata": {
                "text": "Member must complete at least 6 WEEKS of conservative therapy...",
                "rule_type": "conservative_treatment",
                "is_requirement": True,
                "is_exception": False,
                "logical_operator": "TWO",
                "section_header": "CONSERVATIVE TREATMENT REQUIREMENT",
            },
            "score": 0.85
        },
        {
            "metadata": {
                "text": "EXCEPTIONS to conservative treatment: Suspected ACL rupture...",
                "rule_type": "conservative_treatment",
                "is_requirement": False,
                "is_exception": True,
                "logical_operator": None,
                "section_header": "EXCEPTIONS",
                "icd_codes": ["S83.5xx"]
            },
            "score": 0.80
        },
        {
            "metadata": {
                "text": "For questions: Aetna Prior Authorization Department...",
                "rule_type": "admin",
                "is_requirement": False,
                "is_exception": False,
                "section_header": "CONTACT INFO",
            },
            "score": 0.75
        }
    ]
    
    reranker = Reranker()
    
    # Test 1: Exception query
    print("="*80)
    print("TEST 1: Exception Query")
    print("="*80)
    
    query1 = "Can I skip PT if I tore my ACL?"
    results1 = reranker.rerank(query1, mock_candidates, top_k=3, verbose=True)
    
    # Test 2: Requirement query
    print("\n" + "="*80)
    print("TEST 2: Requirement Query")
    print("="*80)
    
    query2 = "What are the requirements for conservative treatment?"
    results2 = reranker.rerank(query2, mock_candidates, top_k=3, verbose=True)