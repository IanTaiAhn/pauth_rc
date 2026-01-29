# chunking/improved_chunker.py
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class PolicyChunk:
    """Structured representation of a policy chunk with rich metadata"""
    chunk_id: str
    text: str
    rule_type: str
    section_header: str
    parent_context: Optional[str] = None  # Parent rule this belongs to
    logical_operator: Optional[str] = None  # "ALL", "ONE", "ANY", etc.
    is_exception: bool = False
    is_requirement: bool = False
    is_definition: bool = False
    cpt_codes: List[str] = None
    icd_codes: List[str] = None
    
    def __post_init__(self):
        if self.cpt_codes is None:
            self.cpt_codes = []
        if self.icd_codes is None:
            self.icd_codes = []
    
    def to_dict(self):
        return asdict(self)


class InsurancePolicyChunker:
    """
    Specialized chunker for insurance policy documents that preserves
    hierarchical structure and semantic relationships.
    """
    
    # Patterns for identifying different section types
    SECTION_PATTERNS = [
        (r"SECTION\s+\d+.*POLICY STATEMENT", "policy_statement"),
        (r"SECTION\s+\d+.*PRIOR AUTHORIZATION", "pa_requirements"),
        (r"COVERAGE CRITERIA", "coverage_criteria"),
        (r"DIAGNOSIS REQUIREMENT", "diagnosis_requirement"),
        (r"CLINICAL FINDINGS", "clinical_findings"),
        (r"IMAGING REQUIREMENT", "imaging_requirement"),
        (r"CONSERVATIVE TREATMENT", "conservative_treatment"),
        (r"EXCEPTIONS?", "exceptions"),
        (r"AGE CONSIDERATIONS", "age_rules"),
        (r"PRIOR IMAGING", "prior_imaging"),
        (r"NOT MEDICALLY NECESSARY", "exclusions"),
        (r"DOCUMENTATION REQUIREMENTS?", "documentation"),
        (r"SPECIAL POPULATIONS", "special_populations"),
        (r"FREQUENTLY ASKED QUESTIONS", "faq"),
    ]
    
    def __init__(self, tokenizer, max_tokens=400, min_chunk_tokens=100):
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens
        self.min_chunk_tokens = min_chunk_tokens
        
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))
    
    def extract_codes(self, text: str) -> tuple[List[str], List[str]]:
        """Extract CPT and ICD codes from text"""
        # CPT codes: 5 digits
        cpt_codes = re.findall(r'\b\d{5}\b', text)
        # ICD-10 codes: Letter followed by digits and possibly dots/x
        icd_codes = re.findall(r'\b[A-Z]\d{2}\.?[\dxX]+\b', text)
        return cpt_codes, icd_codes
    
    def detect_logical_operator(self, text: str) -> Optional[str]:
        """Detect logical operators (ALL, ONE, ANY) in requirements"""
        text_upper = text.upper()
        if re.search(r'\bALL\s+(?:OF\s+)?THE\s+FOLLOWING', text_upper):
            return "ALL"
        elif re.search(r'\bAT\s+LEAST\s+ONE', text_upper):
            return "ONE"
        elif re.search(r'\bAT\s+LEAST\s+TWO', text_upper):
            return "TWO"
        elif re.search(r'\bANY\s+OF', text_upper):
            return "ANY"
        return None
    
    def is_list_item(self, text: str) -> bool:
        """Check if text is a list item"""
        return bool(re.match(r'^\s*[-•*]\s+', text) or re.match(r'^\s*\d+[\.)]\s+', text))
    
    def extract_hierarchical_sections(self, text: str) -> List[Dict]:
        """
        Parse document into hierarchical sections with parent-child relationships.
        This is the key improvement - we maintain structure.
        """
        lines = text.split('\n')
        sections = []
        current_section = None
        current_subsection = None
        parent_context = None
        
        for line in lines:
            line = line.strip()
            if not line or line == '=' * len(line):
                continue
            
            # Check if this is a major section header (ALL CAPS, ends with colon or is SECTION X)
            if re.match(r'^(SECTION\s+\d+:|[A-Z][A-Z\s\-/()]{10,}:?)$', line):
                # This is a new major section
                current_section = {
                    'header': line,
                    'rule_type': self._detect_rule_type(line),
                    'content': [],
                    'subsections': []
                }
                sections.append(current_section)
                parent_context = line
                current_subsection = None
                
            # Check if this is a subsection header (shorter caps, likely indented)
            elif current_section and re.match(r'^[A-Z][A-Z\s\-/()]{3,}:?$', line) and len(line) < 50:
                current_subsection = {
                    'header': line,
                    'rule_type': self._detect_rule_type(line),
                    'content': [],
                    'parent': parent_context
                }
                current_section['subsections'].append(current_subsection)
                
            # Otherwise it's content
            else:
                if current_subsection:
                    current_subsection['content'].append(line)
                elif current_section:
                    current_section['content'].append(line)
        
        return sections
    
    def _detect_rule_type(self, header: str) -> str:
        """Detect the type of rule from header text"""
        header_upper = header.upper()
        for pattern, rule_type in self.SECTION_PATTERNS:
            if re.search(pattern, header_upper):
                return rule_type
        return "general"
    
    def chunk_list_intelligently(self, items: List[str], header: str, 
                                  parent_context: str) -> List[str]:
        """
        Chunk a list while keeping semantic units together.
        For example, keep all diagnosis codes together, or all conservative
        treatment options together if they fit.
        """
        chunks = []
        current_chunk = []
        current_tokens = self.count_tokens(header + " " + parent_context)
        
        for item in items:
            item_tokens = self.count_tokens(item)
            
            # If adding this item would exceed max_tokens, flush current chunk
            if current_tokens + item_tokens > self.max_tokens and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [item]
                current_tokens = self.count_tokens(header + " " + parent_context + " " + item)
            else:
                current_chunk.append(item)
                current_tokens += item_tokens
        
        if current_chunk:
            chunks.append("\n".join(current_chunk))
        
        return chunks
    
    def create_chunk_with_context(self, content: str, header: str, 
                                   rule_type: str, parent_context: Optional[str] = None,
                                   chunk_id: str = None) -> PolicyChunk:
        """
        Create a chunk with full context prepended.
        KEY INSIGHT: Always include parent context so retrieval has full picture.
        """
        # Build the full text with context
        context_parts = []
        if parent_context and parent_context != header:
            context_parts.append(parent_context)
        context_parts.append(header)
        context_parts.append(content)
        
        full_text = "\n".join(context_parts)
        
        # Extract codes
        cpt_codes, icd_codes = self.extract_codes(full_text)
        
        # Detect properties
        logical_op = self.detect_logical_operator(full_text)
        is_exception = "EXCEPTION" in header.upper()
        is_requirement = "REQUIREMENT" in header.upper() and not is_exception
        is_definition = "DEFINITION" in header.upper() or "CLARIFICATION" in header.upper()
        
        return PolicyChunk(
            chunk_id=chunk_id or f"{rule_type}_{hash(full_text) % 10000}",
            text=full_text,
            rule_type=rule_type,
            section_header=header,
            parent_context=parent_context,
            logical_operator=logical_op,
            is_exception=is_exception,
            is_requirement=is_requirement,
            is_definition=is_definition,
            cpt_codes=cpt_codes,
            icd_codes=icd_codes
        )
    
    def chunk_subsection(self, subsection: Dict, parent_header: str) -> List[PolicyChunk]:
        """
        Chunk a subsection while preserving its relationship to parent section.
        """
        chunks = []
        header = subsection['header']
        rule_type = subsection['rule_type']
        content = subsection['content']
        parent_context = subsection.get('parent', parent_header)
        
        # Join content
        full_content = "\n".join(content)
        
        # Check if content is a list
        list_items = [line for line in content if self.is_list_item(line)]
        
        if list_items and len(list_items) > 3:
            # This is a list - chunk intelligently
            list_chunks = self.chunk_list_intelligently(list_items, header, parent_context)
            
            for i, chunk_text in enumerate(list_chunks):
                chunk = self.create_chunk_with_context(
                    content=chunk_text,
                    header=header,
                    rule_type=rule_type,
                    parent_context=parent_context,
                    chunk_id=f"{rule_type}_{i}"
                )
                chunks.append(chunk)
        else:
            # Regular content - create single chunk if under max_tokens
            chunk = self.create_chunk_with_context(
                content=full_content,
                header=header,
                rule_type=rule_type,
                parent_context=parent_context,
                chunk_id=f"{rule_type}_0"
            )
            
            # If too large, split by sentences
            if self.count_tokens(chunk.text) > self.max_tokens:
                sentences = re.split(r'(?<=[.!?])\s+', full_content)
                current_sents = []
                current_tokens = self.count_tokens(header + " " + parent_context)
                
                for sent in sentences:
                    sent_tokens = self.count_tokens(sent)
                    if current_tokens + sent_tokens > self.max_tokens and current_sents:
                        chunk = self.create_chunk_with_context(
                            content=" ".join(current_sents),
                            header=header,
                            rule_type=rule_type,
                            parent_context=parent_context,
                            chunk_id=f"{rule_type}_{len(chunks)}"
                        )
                        chunks.append(chunk)
                        current_sents = [sent]
                        current_tokens = self.count_tokens(header + " " + parent_context + " " + sent)
                    else:
                        current_sents.append(sent)
                        current_tokens += sent_tokens
                
                if current_sents:
                    chunk = self.create_chunk_with_context(
                        content=" ".join(current_sents),
                        header=header,
                        rule_type=rule_type,
                        parent_context=parent_context,
                        chunk_id=f"{rule_type}_{len(chunks)}"
                    )
                    chunks.append(chunk)
            else:
                chunks.append(chunk)
        
        return chunks
    
    def chunk_document(self, text: str) -> List[Dict]:
        """
        Main entry point: chunk entire document while preserving structure.
        """
        # Step 1: Parse hierarchical structure
        sections = self.extract_hierarchical_sections(text)
        
        # Step 2: Create chunks with full context
        all_chunks = []
        
        for section in sections:
            section_header = section['header']
            section_rule_type = section['rule_type']
            
            # Chunk main section content if any
            if section['content']:
                content_text = "\n".join(section['content'])
                chunk = self.create_chunk_with_context(
                    content=content_text,
                    header=section_header,
                    rule_type=section_rule_type,
                    parent_context=None,
                    chunk_id=f"{section_rule_type}_main"
                )
                if self.count_tokens(chunk.text) <= self.max_tokens:
                    all_chunks.append(chunk.to_dict())
            
            # Chunk subsections
            for subsection in section['subsections']:
                subsection_chunks = self.chunk_subsection(subsection, section_header)
                all_chunks.extend([c.to_dict() for c in subsection_chunks])
        
        return all_chunks


# Example usage
if __name__ == "__main__":
    # Mock tokenizer for testing
    class MockTokenizer:
        def encode(self, text):
            return text.split()
    
    tokenizer = MockTokenizer()
    chunker = InsurancePolicyChunker(tokenizer, max_tokens=400)
    
    sample_text = """
SECTION 2: KNEE MRI - PRIOR AUTHORIZATION REQUIREMENTS

CPT Codes: 73721, 73722, 73723

COVERAGE CRITERIA:

MRI of the knee is considered MEDICALLY NECESSARY when ALL of the following
criteria are met:

DIAGNOSIS REQUIREMENT:
Member must have a documented diagnosis consistent with one of the following:

- Suspected meniscal tear (ICD-10: M23.2xx, M23.3xx)
- Suspected ligamentous injury (ICD-10: S83.5xx, S83.6xx)
- Knee pain with mechanical symptoms (ICD-10: M25.56x)

CONSERVATIVE TREATMENT REQUIREMENT:
Member must have completed at least 6 WEEKS (42 days) of conservative
therapy, including at least TWO of the following:

- Physical therapy (minimum 6 sessions documented)
- NSAIDs or analgesics (trial of at least 4 weeks)

EXCEPTIONS to conservative treatment requirement:

- Suspected complete ligament rupture (ACL, PCL, MCL, LCL)
- Acute traumatic injury with inability to bear weight
    """
    
    chunks = chunker.chunk_document(sample_text)
    
    print(f"Created {len(chunks)} chunks:\n")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}:")
        print(f"  Rule Type: {chunk['rule_type']}")
        print(f"  Header: {chunk['section_header']}")
        print(f"  Parent: {chunk['parent_context']}")
        print(f"  Logical Op: {chunk['logical_operator']}")
        print(f"  Is Exception: {chunk['is_exception']}")
        print(f"  Text preview: {chunk['text'][:100]}...")
        print()