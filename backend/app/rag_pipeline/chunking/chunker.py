# chunking/chunker.py
import re
from typing import List, Dict


# --------------------------------------------------
# 1. Sentence splitter (same idea, slightly safer)
# --------------------------------------------------
def sentence_split(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


# --------------------------------------------------
# 2. Detect section headers and assign rule types
# --------------------------------------------------
SECTION_PATTERNS = [
    (r"SECTION\s+\d+.*POLICY STATEMENT", "policy_statement"),
    (r"SECTION\s+\d+.*PRIOR AUTHORIZATION REQUIREMENTS?", "pa_requirements"),
    (r"COVERAGE CRITERIA", "coverage_criteria"),
    (r"DIAGNOSIS REQUIREMENT", "diagnosis_requirement"),
    (r"CLINICAL FINDINGS", "clinical_findings"),
    (r"IMAGING REQUIREMENT", "imaging_requirement"),
    (r"CONSERVATIVE TREATMENT REQUIREMENT", "conservative_treatment"),
    (r"EXCEPTIONS", "exceptions"),
    (r"AGE CONSIDERATIONS", "age_rules"),
    (r"PRIOR IMAGING", "prior_imaging"),
    (r"NOT MEDICALLY NECESSARY", "not_medically_necessary"),
    (r"DOCUMENTATION REQUIREMENTS", "documentation"),
    (r"AUTHORIZATION VALIDITY", "admin"),
    (r"APPENDIX", "appendix"),
]


def detect_rule_type(header_text: str) -> str:
    header_text = header_text.upper()
    for pattern, rule_type in SECTION_PATTERNS:
        if re.search(pattern, header_text):
            return rule_type
    return "general"


# --------------------------------------------------
# 3. Split document by headers first
# --------------------------------------------------
HEADER_REGEX = re.compile(
    r"(SECTION\s+\d+:[^\n]+|[A-Z][A-Z \-/()]{3,}:)",
    re.MULTILINE
)


def split_by_headers(text: str) -> List[Dict]:
    parts = HEADER_REGEX.split(text)
    sections = []

    current_header = "GENERAL"
    current_rule_type = "general"

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # If this part looks like a header
        if HEADER_REGEX.match(part):
            current_header = part
            current_rule_type = detect_rule_type(part)
        else:
            sections.append({
                "header": current_header,
                "rule_type": current_rule_type,
                "text": part
            })

    return sections


# --------------------------------------------------
# 4. Token-aware chunking WITHIN each section
# --------------------------------------------------
def chunk_section_text(section: Dict, tokenizer, max_tokens=400, overlap=80, min_chunk_tokens=120):
    sentences = sentence_split(section["text"])

    chunks = []
    current_sents = []
    current_tokens = 0
    chunk_id = 0

    def count_tokens(s):
        return len(tokenizer.encode(s))

    def flush():
        nonlocal chunk_id
        if not current_sents:
            return
        chunk_text = " ".join(current_sents).strip()
        chunks.append({
            "chunk_id": f"{section['rule_type']}_{chunk_id}",
            "text": chunk_text,
            "metadata": {
                "header": section["header"],
                "rule_type": section["rule_type"]
            }
        })
        chunk_id += 1

    for sent in sentences:
        t = count_tokens(sent)

        if current_tokens + t <= max_tokens:
            current_sents.append(sent)
            current_tokens += t
        else:
            if current_tokens >= min_chunk_tokens:
                flush()

                # build overlap
                overlap_sents = []
                overlap_tokens = 0
                for s in reversed(current_sents):
                    st = count_tokens(s)
                    if overlap_tokens + st > overlap:
                        break
                    overlap_sents.insert(0, s)
                    overlap_tokens += st

                current_sents = overlap_sents + [sent]
                current_tokens = overlap_tokens + t
            else:
                current_sents.append(sent)
                current_tokens += t

    if current_sents:
        flush()

    return chunks


# --------------------------------------------------
# 5. Main entry point
# --------------------------------------------------
def chunk_text(text: str, tokenizer) -> List[Dict]:
    # Normalize whitespace
    text = " ".join(text.split())

    # Step 1 — split by policy structure
    sections = split_by_headers(text)

    # Step 2 — chunk inside each section
    all_chunks = []
    for section in sections:
        section_chunks = chunk_section_text(section, tokenizer)
        all_chunks.extend(section_chunks)

    return all_chunks
