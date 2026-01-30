# Reranker Enhancement Guide

## What's New in the Enhanced Reranker

Your original reranker was already pretty good! Here's what I've added to make it work better with the improved chunker's metadata:

---

## Key Improvements

### 1. **Metadata-Aware Boosting** (NEW!)

**Original:** Only used rule_type and keywords
**Enhanced:** Uses ALL the rich metadata from improved chunker

```python
# NEW metadata boosts:
- is_exception: 1.5x boost when query seeks exceptions
- is_requirement: 1.3x boost when query seeks requirements  
- logical_operator: 1.1x boost (shows it's structured)
- code matching: 2.0x boost for exact CPT/ICD matches
- parent_context: 1.1x boost (more complete chunks)
```

### 2. **Query Intent Analysis** (NEW!)

The reranker now understands what the user is asking for:

```python
query_intent = {
    'seeks_exception': True,      # "Can I skip PT?"
    'seeks_requirement': False,   # "What's required?"
    'seeks_definition': False,    # "What does X mean?"
    'mentions_codes': True,       # Contains ICD/CPT codes
    'mentions_age': False,        # Age-related query
    'seeks_comprehensive': False  # "All requirements"
}
```

Then boosts chunks that match the intent!

### 3. **Smart Exception Handling** (NEW!)

```python
# If user asks "Can I skip X?"
if query_intent['seeks_exception']:
    if chunk['is_exception']:
        boost *= 1.5  # BOOST exceptions
    elif chunk['is_requirement']:
        boost *= 0.7  # DEMOTE requirements
```

This ensures exception queries get exception chunks first!

### 4. **Code Matching** (NEW!)

```python
# Query: "I have ICD code S83.511A"
# Chunk has: ["S83.5xx"]
# Matches wildcard pattern → 2.0x BOOST!
```

### 5. **Specialized Criteria Extraction** (NEW!)

Added `rerank_for_criteria_extraction()` method:
- Filters to only requirements/exceptions
- Prioritizes exceptions > requirements
- Ensures comprehensive coverage

---

## Side-by-Side Comparison

### Original Reranker
```python
def rerank(self, query, candidates, top_k=5):
    # 1. Get CrossEncoder scores
    scores = self.model.predict(pairs)
    
    # 2. Apply rule type weight
    type_weight = RULE_TYPE_WEIGHTS.get(rule_type, 1.0)
    
    # 3. Apply keyword boost
    kw_boost = self.keyword_boost(text)
    
    # 4. Combine
    final_score = base_score * type_weight * kw_boost
```

### Enhanced Reranker
```python
def rerank(self, query, candidates, top_k=5):
    # 1. Analyze query intent (NEW!)
    query_intent = self.analyze_query_intent(query)
    
    # 2. Get CrossEncoder scores
    scores = self.model.predict(pairs)
    
    # 3. Apply rule type weight
    type_weight = RULE_TYPE_WEIGHTS.get(rule_type, 1.0)
    
    # 4. Apply keyword boost
    kw_boost = self.keyword_boost(text)
    
    # 5. Apply metadata boost (NEW!)
    meta_boost = self.metadata_boost(
        candidate, 
        query_intent,
        query_codes
    )
    
    # 6. Combine all factors
    final_score = base_score * type_weight * kw_boost * meta_boost
```

---

## Integration Steps

### Step 1: Update Rule Type Weights

I've added new rule types from the improved chunker:

```python
RULE_TYPE_WEIGHTS = {
    # NEW types
    "exceptions": 1.35,           # ← Boosted! Very important
    "special_populations": 1.15,  # ← NEW
    "pa_requirements": 1.2,       # ← NEW
    "faq": 0.85,                  # ← NEW
    
    # Existing types (some weights adjusted)
    "coverage_criteria": 1.4,     # ← Increased from 1.3
    "conservative_treatment": 1.3, # ← Increased from 1.2
    # ... rest of your weights
}
```

### Step 2: Replace Your Reranker File

```bash
# Backup original
cp backend/app/rag_pipeline/retrieval/reranker.py \
   backend/app/rag_pipeline/retrieval/reranker_OLD.py

# Use enhanced version
cp reranker_enhanced.py \
   backend/app/rag_pipeline/retrieval/reranker.py
```

### Step 3: Update Your Retrieval Pipeline

**Before:**
```python
# In your retrieval code
from backend.app.rag_pipeline.retrieval.reranker import Reranker

reranker = Reranker()

# Get candidates from vector search
candidates = store.search(query_vector, k=20)

# Rerank
results = reranker.rerank(query, candidates, top_k=5)
```

**After (no changes needed!):**
```python
# Same code - enhanced reranker is backward compatible!
from backend.app.rag_pipeline.retrieval.reranker import Reranker

reranker = Reranker()
candidates = store.search(query_vector, k=20)
results = reranker.rerank(query, candidates, top_k=5)

# NEW: Add verbose=True to see scoring details
# results = reranker.rerank(query, candidates, top_k=5, verbose=True)
```

### Step 4: For Criteria Extraction (Optional)

If you're using the reranker for criteria extraction:

```python
# Use the specialized method
criteria_chunks = reranker.rerank_for_criteria_extraction(
    query="What are the requirements for knee MRI?",
    candidates=all_chunks,
    top_k=10  # Get more chunks for comprehensive coverage
)
```

---

## Expected Format of Candidates

The enhanced reranker expects candidates in this format:

```python
candidates = [
    {
        "metadata": {
            # Original fields (already have these)
            "text": "chunk text here...",
            "chunk_id": "...",
            "doc_name": "...",
            
            # NEW fields from improved chunker
            "rule_type": "conservative_treatment",
            "section_header": "CONSERVATIVE TREATMENT REQUIREMENT",
            "parent_context": "COVERAGE CRITERIA",
            "logical_operator": "TWO",
            "is_exception": False,
            "is_requirement": True,
            "is_definition": False,
            "cpt_codes": ["73721", "73722"],
            "icd_codes": ["M23.2xx", "S83.5xx"]
        },
        "score": 0.85  # From retrieval
    },
    # ... more candidates
]
```

**Important:** If your candidates don't have the new metadata fields yet, the reranker will still work! It gracefully handles missing fields with `.get()` calls.

---

## Testing the Enhanced Reranker

### Test 1: Exception Query

```python
query = "Can I get knee MRI without physical therapy?"

# Expected behavior:
# - Detect seeks_exception = True
# - Boost exception chunks 1.5x
# - Demote requirement chunks 0.7x
# - Top result should be EXCEPTIONS chunk
```

### Test 2: Code Query

```python
query = "Does ICD code S83.511A qualify for knee MRI?"

# Expected behavior:
# - Extract code S83.511A from query
# - Match against chunk codes ["S83.5xx"]
# - Apply 2.0x boost for code match
# - Top result should be DIAGNOSIS REQUIREMENT chunk
```

### Test 3: Comprehensive Query

```python
query = "What are ALL the requirements for knee MRI authorization?"

# Expected behavior:
# - Detect seeks_comprehensive = True
# - Boost chunks with logical_operator="ALL"
# - Return multiple requirement chunks
```

### Test Script

```python
from backend.app.rag_pipeline.retrieval.reranker import Reranker
from backend.app.rag_pipeline.retrieval.enhanced_retrieval import retrieve_with_metadata_boost
from backend.app.rag_pipeline.build_index import load_index, STORE, EMBEDDER

# Load index
load_index("your_index_name")

# Initialize reranker
reranker = Reranker()

# Test query
query = "Can I skip conservative treatment if I tore my ACL?"

# Get candidates from retrieval
candidates = retrieve_with_metadata_boost(
    query=query,
    store=STORE,
    embedder=EMBEDDER,
    top_k=20,
    final_k=20  # Get all candidates for reranking
)

# Convert to reranker format
reranker_candidates = [
    {"metadata": chunk, "score": chunk.get('boosted_score', 1.0)}
    for chunk in candidates
]

# Rerank with verbose output
results = reranker.rerank(
    query=query,
    candidates=reranker_candidates,
    top_k=5,
    verbose=True  # See detailed scoring
)

# Check results
print("\n" + "="*80)
print("FINAL TOP 5 RESULTS")
print("="*80 + "\n")

for i, result in enumerate(results, 1):
    meta = result['metadata']
    print(f"{i}. {meta.get('section_header', 'N/A')}")
    print(f"   Rule Type: {meta.get('rule_type', 'N/A')}")
    print(f"   Is Exception: {meta.get('is_exception', False)}")
    print(f"   Score: {result['rerank_score']:.4f}")
    print()
```

---

## Troubleshooting

### Issue: "Model not found"

```
Warning: Could not load CrossEncoder model
Falling back to metadata-only reranking
```

**Solution:** The reranker will still work using metadata boosting only. If you want CrossEncoder:

```bash
# Install sentence-transformers if not installed
pip install sentence-transformers

# Download a CrossEncoder model
python -c "
from sentence_transformers import CrossEncoder
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')
model.save('backend/app/rag_pipeline/models/minilm_reranker')
"
```

### Issue: Missing metadata fields

If you haven't rebuilt the index yet, chunks won't have new metadata fields.

**Temporary fix:** Reranker handles this gracefully with `.get()` defaults

**Proper fix:** Rebuild index with improved chunker

### Issue: Candidates in wrong format

Error: `'list' object has no attribute 'get'`

**Fix:** Ensure candidates have this structure:
```python
[{"metadata": {...}, "score": 0.85}, ...]
```

Not:
```python
[{...}, ...]  # metadata at top level
```

---

## Performance Tuning

### Adjust Boost Factors

If exception chunks aren't ranking high enough:

```python
# In metadata_boost() method
if query_intent['seeks_exception'] and metadata.get('is_exception'):
    boost *= 2.0  # Increase from 1.5 to 2.0
```

### Adjust Rule Type Weights

If a certain rule type is too high/low:

```python
RULE_TYPE_WEIGHTS = {
    "exceptions": 1.5,  # Increase if exceptions rank too low
    "documentation": 0.4,  # Decrease if docs rank too high
}
```

### Tune Top-K

```python
# Retrieve more for reranking
candidates = retrieve_with_metadata_boost(..., top_k=30)

# Rerank to top 5
results = reranker.rerank(query, candidates, top_k=5)
```

Sweet spot: retrieve 3-5x more than final top_k

---

## Backward Compatibility

✅ **The enhanced reranker is backward compatible!**

If you're not ready to rebuild the index:
- Missing metadata fields default to None
- Boosting gracefully degrades
- Still uses rule_type and keyword boosting

When you rebuild with improved chunker:
- All metadata boosts activate automatically
- No code changes needed!

---

## Summary of Changes

| Feature | Original | Enhanced |
|---------|----------|----------|
| **Rule type boosting** | ✓ | ✓ (expanded) |
| **Keyword boosting** | ✓ | ✓ (enhanced) |
| **Query intent analysis** | ✗ | ✓ NEW |
| **Exception detection** | ✗ | ✓ NEW |
| **Code matching** | ✗ | ✓ NEW |
| **Logical operator awareness** | ✗ | ✓ NEW |
| **Metadata alignment** | ✗ | ✓ NEW |
| **Criteria extraction mode** | ✗ | ✓ NEW |
| **Verbose debugging** | ✗ | ✓ NEW |

---

## Next Steps

1. ✅ Replace reranker.py with enhanced version
2. ✅ Test with verbose=True to see scoring
3. ✅ Tune boost factors based on your use case
4. ✅ Rebuild index (if not done yet) to get full benefit
5. ✅ Consider using rerank_for_criteria_extraction() for automated evaluation

The enhanced reranker will work immediately and get even better once you rebuild the index with the improved chunker! 🚀