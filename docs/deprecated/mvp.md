# Prior Authorization Readiness Checker - RAG-First MVP

## Scope
- **Payer**: Single insurance (e.g., Aetna)
- **Procedures**: 5-10 common CPT codes
- **Rules**: Retrieved from vector DB, structured by LLM
- **Goal**: Validate RAG → Structure → Compare pipeline

---

## RAG-First Architecture

┌─────────────────────────────────────────────────────────────────┐
│                        USER UPLOADS CHART                        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    📄 EVIDENCE EXTRACTION                        │
│                                                                  │
│  LLM: Qwen with strict JSON schema                             │
│  Output: evidence.json                                         │
│  {                                                              │
│    "payer": "aetna",                                           │
│    "cpt_code": "72148",                                        │
│    "diagnosis_codes": ["M25.561"],                            │
│    "patient_age": 45,                                          │
│    "bmi": 28.5,                                                │
│    "prior_treatments": {                                       │
│      "physical_therapy": {                                     │
│        "completed": true,                                      │
│        "duration_days": 56                                     │
│      }                                                          │
│    },                                                           │
│    "symptom_duration_days": 90                                 │
│  }                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                 🔍 RAG POLICY RETRIEVAL                         │
│                                                                  │
│  Query Construction (combine multiple fields):                 │
│   "Aetna prior authorization knee MRI CPT 72148 requirements"  │
│                                                                  │
│  Vector DB Query:                                              │
│   - Embedding model: text-embedding-3-large or similar         │
│   - Top K: 5-10 chunks                                         │
│   - Filters: payer="aetna", cpt_code="72148" (metadata)       │
│                                                                  │
│  Retrieved Chunks Example:                                     │
│  [                                                              │
│    {                                                            │
│      "text": "MRI of the knee requires documented knee pain    │
│               or injury with ICD-10 codes M25.561, M25.562,   │
│               or S83.2xx. Conservative treatment including     │
│               physical therapy must be attempted for at least  │
│               6 weeks unless contraindicated.",                │
│      "source": "aetna_radiology_policy_2024.pdf",             │
│      "page": 23,                                               │
│      "score": 0.89                                             │
│    },                                                           │
│    {                                                            │
│      "text": "Contraindications to conservative care include   │
│               suspected fracture, dislocation, or acute        │
│               ligament tear requiring surgical evaluation.",   │
│      "source": "aetna_radiology_policy_2024.pdf",             │
│      "page": 24,                                               │
│      "score": 0.82                                             │
│    }                                                            │
│  ]                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              🤖 LLM POLICY RULE STRUCTURER                      │
│                                                                  │
│  LLM: GPT-4 or Claude with structured output                  │
│                                                                  │
│  System Prompt:                                                │
│  "You are a medical policy parser. Convert the following       │
│   insurance policy text into structured authorization criteria.│
│   Extract ONLY explicit requirements. Do not infer or add      │
│   criteria not stated in the text."                            │
│                                                                  │
│  Input: Retrieved chunks + evidence.json context               │
│                                                                  │
│  Required JSON Schema:                                         │
│  {                                                              │
│    "criteria": [                                               │
│      {                                                          │
│        "id": "unique_identifier",                              │
│        "category": "diagnosis|clinical|prior_treatment|...",   │
│        "field": "diagnosis_codes",  # Maps to evidence.json    │
│        "operator": "contains_any",                             │
│        "value": ["M25.561", "M25.562", "S83.2"],             │
│        "description": "Qualifying knee diagnosis required",    │
│        "citation": "Page 23, Aetna Radiology Policy 2024"     │
│      },                                                         │
│      {                                                          │
│        "id": "pt_requirement",                                 │
│        "category": "prior_treatment",                          │
│        "field": "prior_treatments.physical_therapy.duration_days",│
│        "operator": "gte",                                      │
│        "value": 42,                                            │
│        "description": "At least 6 weeks of PT required",       │
│        "exceptions": "Unless contraindicated or fracture suspected",│
│        "citation": "Page 23, Aetna Radiology Policy 2024"     │
│      }                                                          │
│    ],                                                           │
│    "logic": "AND",                                             │
│    "policy_source": "aetna_radiology_policy_2024.pdf",        │
│    "confidence": "high|medium|low",                            │
│    "ambiguities": ["Conservative care definition unclear"]     │
│  }                                                              │
│                                                                  │
│  Output: structured_criteria.json                              │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              ⚙️ DETERMINISTIC EVALUATION ENGINE                 │
│                                                                  │
│  Python rule evaluator (NO LLM)                                │
│                                                                  │
│  def evaluate_criterion(evidence, criterion):                  │
│      evidence_value = get_nested_value(                        │
│          evidence, criterion['field']                          │
│      )                                                          │
│      if evidence_value is None:                                │
│          return {"status": "MISSING", ...}                     │
│                                                                  │
│      passed = apply_operator(                                  │
│          evidence_value,                                       │
│          criterion['operator'],                                │
│          criterion['value']                                    │
│      )                                                          │
│      return {                                                   │
│          "status": "MET" if passed else "NOT_MET",            │
│          "evidence_found": evidence_value,                     │
│          "requirement": criterion['description']               │
│      }                                                          │
│                                                                  │
│  Output: evaluation_results.json                               │
│  {                                                              │
│    "authorization_status": "DENIED",                           │
│    "criteria_results": [                                       │
│      {                                                          │
│        "criterion_id": "diagnosis_check",                      │
│        "status": "MET",                                        │
│        "evidence_found": ["M25.561"],                         │
│        "requirement": "Qualifying knee diagnosis required",    │
│        "citation": "Page 23..."                                │
│      },                                                         │
│      {                                                          │
│        "criterion_id": "pt_requirement",                       │
│        "status": "NOT_MET",                                    │
│        "evidence_found": 28,                                   │
│        "evidence_required": 42,                                │
│        "gap": "14 days short",                                 │
│        "requirement": "At least 6 weeks of PT required",       │
│        "citation": "Page 23..."                                │
│      }                                                          │
│    ],                                                           │
│    "overall_approved": false,                                  │
│    "confidence": "high"                                        │
│  }                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              ✍️ JUSTIFICATION GENERATOR                         │
│                                                                  │
│  LLM: GPT-4/Claude                                             │
│  Input: evaluation_results.json + evidence.json                │
│                                                                  │
│  Template-guided generation:                                   │
│  "Write a professional prior authorization determination       │
│   letter. State the decision clearly, cite specific policy     │
│   requirements, and explain what evidence was found vs needed."│
│                                                                  │
│  Output: Formatted letter with:                                │
│   - Decision summary                                           │
│   - Met criteria (with evidence)                               │
│   - Unmet criteria (with gaps)                                 │
│   - Next steps if denied                                       │
│   - Policy citations                                           │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    📋 USER INTERFACE                            │
└─────────────────────────────────────────────────────────────────┘

---

## Critical RAG Implementation Details

### 1. Vector DB Indexing Strategy

Chunk your policy documents with:
- **Chunk size**: 500-1000 tokens with 100 token overlap
- **Metadata per chunk**:
```python
  {
    "payer": "aetna",
    "cpt_code": "72148",  # May be multiple
    "category": "radiology",
    "document_title": "Aetna Radiology Policy 2024",
    "page": 23,
    "last_updated": "2024-01-15"
  }
```

### 2. Query Strategy (Hybrid)

Don't just do semantic search. Combine:
```python
# Metadata pre-filter
filters = {
    "payer": evidence["payer"],
    "cpt_code": evidence["cpt_code"]
}

# Semantic query
query = f"""
Prior authorization requirements for {evidence['cpt_code']} 
with diagnosis {evidence['diagnosis_codes']} 
for {evidence['payer']}
"""

# Execute
chunks = vector_db.query(
    query=query,
    filters=filters,
    top_k=10,
    score_threshold=0.75
)
```

### 3. LLM Structurer Prompt (Critical!)
```python
STRUCTURER_PROMPT = """
You are parsing insurance prior authorization policies into structured criteria.

POLICY TEXT:
{retrieved_chunks}

PATIENT EVIDENCE AVAILABLE:
{evidence_json}

Your task:
1. Extract ONLY explicit authorization requirements from the policy text
2. Map each requirement to a field in the patient evidence JSON
3. Identify the operator needed (contains, >=, exists, etc.)
4. Note any exceptions or special cases
5. Cite the source page/section

CRITICAL RULES:
- Only extract criteria explicitly stated in the policy
- Do not infer unstated requirements
- If a requirement references a field not in evidence schema, note it in "unmapped_criteria"
- Mark confidence as "low" if policy language is ambiguous

Output strictly valid JSON matching this schema:
{criteria_schema}
"""
```

### 4. Operator Implementation
```python
def apply_operator(evidence_value, operator, required_value):
    operators = {
        'equals': lambda e, r: e == r,
        'contains': lambda e, r: r in e,
        'contains_any': lambda e, r: any(item in e for item in r),
        'gte': lambda e, r: float(e) >= float(r),
        'lte': lambda e, r: float(e) <= float(r),
        'exists': lambda e, r: e is not None,
        'duration_days_gte': lambda e, r: e.get('duration_days', 0) >= r,
    }
    return operators[operator](evidence_value, required_value)
```

---

## Prototype Testing Plan

### Test with 3 scenarios per CPT code:

**Scenario 1: Clear Approval**
- All criteria met with strong evidence
- Tests: RAG retrieval + structuring + positive evaluation

**Scenario 2: Clear Denial**  
- Missing key criterion (e.g., no PT documented)
- Tests: Gap identification + justification quality

**Scenario 3: Ambiguous/Incomplete**
- Evidence present but unclear (e.g., "some PT done" without duration)
- Tests: MISSING status handling + what to request

### Metrics to track:
```python
{
    "rag_retrieval_quality": {
        "relevant_chunks_retrieved": 8/10,  # Manual review
        "avg_relevance_score": 0.84
    },
    "structuring_quality": {
        "criteria_correctly_extracted": 9/10,  # vs manual parsing
        "false_criteria_added": 1/10,
        "field_mapping_accuracy": 8/10
    },
    "evaluation_accuracy": {
        "correct_decisions": 27/30,  # vs manual adjudication
        "false_approvals": 1/30,
        "false_denials": 2/30
    }
}
```

---

## Known Issues to Watch For

### 1. **RAG Retrieval Failures**
- Policy split across non-contiguous chunks
- **Mitigation**: Increase top_k, add re-ranking

### 2. **LLM Structuring Hallucinations**
- LLM invents criteria not in policy
- **Mitigation**: Strong prompt, require citations, validation layer

### 3. **Field Mapping Errors**
- Policy says "BMI" but evidence has "body_mass_index"
- **Mitigation**: Provide field name glossary to structurer

### 4. **Ambiguous Policy Language**
- "Reasonable trial of therapy" - how many weeks?
- **Mitigation**: Flag ambiguities, use conservative interpretation

---

## Quick Start Implementation
```python
# Minimal end-to-end prototype

def process_authorization(chart_note, payer, cpt_code):
    # 1. Extract evidence
    evidence = extract_evidence(chart_note)
    
    # 2. RAG retrieval
    chunks = vector_db.query(
        query=f"{payer} {cpt_code} prior authorization",
        filters={"payer": payer, "cpt_code": cpt_code},
        top_k=8
    )
    
    # 3. Structure criteria
    criteria = llm_structure_criteria(chunks, evidence)
    
    # 4. Evaluate
    results = evaluate_criteria(evidence, criteria)
    
    # 5. Generate justification
    letter = llm_generate_justification(results, evidence, criteria)
    
    return {
        "decision": results["authorization_status"],
        "letter": letter,
        "debug": {
            "evidence": evidence,
            "criteria": criteria,
            "evaluation": results
        }
    }
```

---

## MVP Success Criteria

✅ **Prototype is successful if:**
1. RAG retrieves relevant policy chunks 80%+ of the time
2. LLM structures criteria correctly 70%+ of the time (vs your manual review)
3. Deterministic engine makes correct approve/deny decisions 75%+ of the time
4. You identify the top 3 failure modes to fix in v2

This gets you to a working system fast while exposing where the real challenges are. Want me to provide example code for any specific component?