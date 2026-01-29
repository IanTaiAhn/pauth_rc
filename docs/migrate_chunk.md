# Migration Guide: Integrating Improved Chunker

This guide walks you through integrating the improved chunker into your existing RAG pipeline.

---

## Step 1: File Organization (5 minutes)

### 1.1 Add the improved chunker to your project

```bash
# Copy improved_chunker.py to your chunking directory
cp improved_chunker.py backend/app/rag_pipeline/chunking/improved_chunker.py
```

### 1.2 Verify your directory structure

```
backend/app/rag_pipeline/
├── chunking/
│   ├── __init__.py
│   ├── chunker.py              # Your old chunker (keep for reference)
│   └── improved_chunker.py     # NEW: The improved chunker
├── embeddings/
│   ├── embedder.py
│   └── vectorstore.py
├── ingestion/
│   ├── pdf_loader.py
│   └── text_loader.py
└── build_index.py              # We'll update this
```

---

## Step 2: Update build_index.py (10 minutes)

### 2.1 Replace the import statement

**OLD:**
```python
from backend.app.rag_pipeline.chunking.chunker import chunk_text
```

**NEW:**
```python
from backend.app.rag_pipeline.chunking.improved_chunker import InsurancePolicyChunker
```

### 2.2 Initialize the chunker in build_index()

**OLD:**
```python
def build_index():
    # ... existing code ...
    
    model_path = str(MODEL_DIR)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    store = None
```

**NEW:**
```python
def build_index():
    # ... existing code ...
    
    model_path = str(MODEL_DIR)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    
    # NEW: Initialize the improved chunker
    chunker = InsurancePolicyChunker(
        tokenizer=tokenizer,
        max_tokens=400,      # Adjust based on your model
        min_chunk_tokens=100
    )
    
    store = None
```

### 2.3 Update the chunking call

**OLD:**
```python
for doc_name, text in docs:
    print(f"\nChunking {doc_name}...")
    
    chunks = chunk_text(
        text,
        tokenizer=tokenizer
    )
    
    chunk_texts = [c["text"] for c in chunks]
```

**NEW:**
```python
for doc_name, text in docs:
    print(f"\nChunking {doc_name}...")
    
    # Use the improved chunker
    chunks = chunker.chunk_document(text)
    
    chunk_texts = [c["text"] for c in chunks]
    
    # Optional: Print statistics
    print(f"  - Created {len(chunks)} chunks")
    print(f"  - {sum(1 for c in chunks if c['is_requirement'])} requirements")
    print(f"  - {sum(1 for c in chunks if c['is_exception'])} exceptions")
```

### 2.4 Update metadata storage

This is **CRITICAL** - you need to store ALL the new metadata fields.

**OLD:**
```python
metadatas = [
    {
        "doc_name": doc_name,
        "chunk_id": c["chunk_id"],
        "text": c["text"]
    }
    for c in chunks
]
```

**NEW:**
```python
metadatas = [
    {
        # Original fields
        "doc_name": str(doc_name),
        "chunk_id": c["chunk_id"],
        "text": c["text"],
        
        # NEW: Rich metadata from improved chunker
        "rule_type": c["rule_type"],
        "section_header": c["section_header"],
        "parent_context": c.get("parent_context"),
        "logical_operator": c.get("logical_operator"),
        "is_exception": c["is_exception"],
        "is_requirement": c["is_requirement"],
        "is_definition": c["is_definition"],
        "cpt_codes": c["cpt_codes"],
        "icd_codes": c["icd_codes"],
    }
    for c in chunks
]
```

### 2.5 Complete updated build_index.py

I've provided the complete file in `build_index_updated.py`. You can either:
- Copy the whole file to replace your current `build_index.py`, OR
- Apply the changes above manually to your existing file

---

## Step 3: Rebuild Your Index (15-30 minutes)

**IMPORTANT:** You MUST rebuild your index with the new chunker to get the benefits.

### 3.1 Backup your old index (optional but recommended)

```bash
# Backup existing index
mv backend/app/rag_pipeline/vectorstore backend/app/rag_pipeline/vectorstore_old_backup
```

### 3.2 Run the index builder

```python
# In your terminal or in a script
from backend.app.rag_pipeline.build_index import build_index

build_index()
```

### 3.3 Verify the new index

```python
from backend.app.rag_pipeline.build_index import load_index, STORE

# Load the new index
load_index("your_index_name")

# Check metadata
if STORE and STORE.metadata:
    sample_chunk = STORE.metadata[0]
    print("Sample chunk metadata:")
    for key, value in sample_chunk.items():
        print(f"  {key}: {value}")
    
    # Verify new fields exist
    assert 'rule_type' in sample_chunk, "Missing rule_type!"
    assert 'is_exception' in sample_chunk, "Missing is_exception!"
    print("\n✓ New metadata fields confirmed!")
```

---

## Step 4: Enhance Your Retrieval (30-60 minutes)

### 4.1 Add the enhanced retrieval module

```bash
# Copy enhanced_retrieval.py to your retrieval directory
cp enhanced_retrieval.py backend/app/rag_pipeline/retrieval/enhanced_retrieval.py
```

### 4.2 Update your existing retrieval code

**Find your current retrieval function** (it probably looks something like this):

**OLD:**
```python
def retrieve_context(query, top_k=5):
    query_vector = embedder.embed([query])[0]
    results = store.search(query_vector, k=top_k)
    
    # Extract texts
    contexts = [metadata['text'] for _, metadata in results]
    return "\n\n".join(contexts)
```

**NEW:**
```python
from backend.app.rag_pipeline.retrieval.enhanced_retrieval import retrieve_and_format

def retrieve_context(query, top_k=5, verbose=False):
    """
    Retrieve context with metadata-aware boosting.
    """
    context = retrieve_and_format(
        query=query,
        store=store,
        embedder=embedder,
        top_k=top_k,
        include_metadata=True,  # Include structural info for LLM
        verbose=verbose  # Set True for debugging
    )
    
    return context
```

### 4.3 Alternative: Gradual migration

If you want to test without breaking existing code:

```python
def retrieve_context(query, top_k=5, use_enhanced=True):
    """
    Retrieve context with optional enhanced retrieval.
    """
    if use_enhanced:
        # Use new metadata-aware retrieval
        from backend.app.rag_pipeline.retrieval.enhanced_retrieval import retrieve_and_format
        context = retrieve_and_format(query, store, embedder, top_k)
    else:
        # Fall back to old method
        query_vector = embedder.embed([query])[0]
        results = store.search(query_vector, k=top_k)
        contexts = [metadata['text'] for _, metadata in results]
        context = "\n\n".join(contexts)
    
    return context
```

---

## Step 5: Update Your LLM Prompt (10 minutes)

The enhanced retrieval includes structural metadata in the context. Update your LLM prompt to use it:

**Example Updated Prompt:**

```python
SYSTEM_PROMPT = """You are an expert assistant for insurance policy questions.

You will be provided with relevant policy sections that may include:
- ✓ REQUIREMENT markers: These are mandatory criteria
- ⚡ EXCEPTION CLAUSE markers: These override normal requirements
- ⚠️ Logical operators: Pay attention to "ALL", "ONE", or "TWO" criteria requirements

When answering:
1. Check for EXCEPTION clauses first - they override requirements
2. Pay attention to logical operators (ALL vs ONE vs TWO)
3. If codes (CPT/ICD) are mentioned, reference them specifically
4. Cite the specific section when giving your answer

Context:
{context}

User Question: {query}

Answer:"""

def generate_answer(query, context):
    prompt = SYSTEM_PROMPT.format(context=context, query=query)
    # ... rest of your LLM call ...
```

---

## Step 6: Testing (30-60 minutes)

### 6.1 Run test queries

Use the test queries I provided earlier:

```python
from backend.app.rag_pipeline.build_index import load_index, STORE, EMBEDDER
from backend.app.rag_pipeline.retrieval.enhanced_retrieval import retrieve_and_format

# Load index
load_index("your_index_name")

# Test queries
test_cases = [
    {
        "query": "Do I need physical therapy before knee MRI?",
        "expected_chunks": ["conservative_treatment"],
        "should_mention": ["6 weeks", "exceptions"]
    },
    {
        "query": "I tore my ACL, do I still need 6 weeks of treatment?",
        "expected_chunks": ["conservative_treatment"],
        "should_mention": ["exception", "ACL", "ligament rupture"]
    },
    {
        "query": "What ICD-10 codes qualify for knee MRI?",
        "expected_chunks": ["diagnosis_requirement"],
        "should_mention": ["M23", "S83", "M17"]
    },
]

for test in test_cases:
    print(f"\n{'='*80}")
    print(f"Query: {test['query']}")
    print(f"{'='*80}\n")
    
    context = retrieve_and_format(
        query=test['query'],
        store=STORE,
        embedder=EMBEDDER,
        top_k=3,
        verbose=True  # Shows boost factors and reasons
    )
    
    # Manual verification
    print("\nExpected to retrieve chunks about:", test['expected_chunks'])
    print("Should mention:", test['should_mention'])
    print("\nActual retrieved context:")
    print(context[:500] + "...")
```

### 6.2 Compare old vs new

If you kept the old index backup:

```python
# Load old index
from backend.app.rag_pipeline.vectorstore import FaissStore
old_store = FaissStore.load(dim, path="vectorstore_old_backup", name="index_name")

# Load new index
new_store = FaissStore.load(dim, path="vectorstore", name="index_name")

# Compare retrieval
query = "Can I skip PT if I tore my ACL?"

# Old retrieval
old_results = old_store.search(embedder.embed([query])[0], k=3)
print("OLD RETRIEVAL:")
for score, meta in old_results:
    print(f"  - {meta.get('text', '')[:100]}")

# New retrieval with boosting
new_results = retrieve_with_metadata_boost(query, new_store, embedder, final_k=3)
print("\nNEW RETRIEVAL:")
for meta in new_results:
    print(f"  - {meta.get('section_header')} (boost: {meta.get('boost_factor')}x)")
    print(f"    {meta.get('text', '')[:100]}")
```

---

## Step 7: Monitor & Iterate (Ongoing)

### 7.1 Add logging to track performance

```python
import logging

logger = logging.getLogger(__name__)

def retrieve_context(query, top_k=5):
    # Retrieve
    chunks = retrieve_with_metadata_boost(query, store, embedder, final_k=top_k)
    
    # Log retrieval details
    logger.info(f"Query: {query}")
    logger.info(f"Top chunks: {[c['rule_type'] for c in chunks]}")
    logger.info(f"Boost factors: {[c.get('boost_factor', 1.0) for c in chunks]}")
    
    # Format and return
    return format_context(chunks)
```

### 7.2 Collect user feedback

Add a feedback mechanism to your frontend:

```python
# In your API endpoint
@app.post("/query")
def query_endpoint(query: str):
    context = retrieve_context(query)
    answer = generate_answer(query, context)
    
    return {
        "answer": answer,
        "chunks_used": [c['section_header'] for c in chunks],
        "feedback_id": save_to_feedback_db(query, chunks, answer)
    }

@app.post("/feedback")
def feedback_endpoint(feedback_id: str, helpful: bool):
    # Track which queries worked well
    log_feedback(feedback_id, helpful)
```

### 7.3 Tune boost factors

Based on feedback, adjust the boost factors in `enhanced_retrieval.py`:

```python
# In retrieve_with_metadata_boost()

# Current values:
if intent['is_exception_query'] and metadata.get('is_exception'):
    boost_factor *= 1.5  # Adjust this

if intent['mentions_codes']:
    if any(code in chunk_codes for code in mentioned_codes):
        boost_factor *= 2.0  # Adjust this
```

---

## Quick Reference: Key Changes Summary

| Component | Old | New |
|-----------|-----|-----|
| **Chunker** | `chunk_text()` function | `InsurancePolicyChunker` class |
| **Chunking call** | `chunk_text(text, tokenizer)` | `chunker.chunk_document(text)` |
| **Metadata** | `doc_name, chunk_id, text` | + `rule_type, is_exception, logical_operator, codes, etc.` |
| **Retrieval** | Simple vector search | Metadata-aware boosting |
| **Context format** | Plain text chunks | Structured with section headers and flags |

---

## Troubleshooting

### Issue: "Module not found: improved_chunker"

**Solution:** Make sure you copied `improved_chunker.py` to the correct location:
```bash
backend/app/rag_pipeline/chunking/improved_chunker.py
```

### Issue: "KeyError: 'rule_type'"

**Solution:** You need to rebuild your index. The old chunks don't have the new metadata fields.

### Issue: "Retrieval quality didn't improve"

**Possible causes:**
1. Index not rebuilt with new chunker
2. Metadata not being used in retrieval (check that you're using `retrieve_with_metadata_boost`)
3. Need to tune boost factors for your specific use case
4. Embedding model quality (consider upgrading)

### Issue: "Chunks are too long/short"

**Solution:** Adjust parameters in `InsurancePolicyChunker`:
```python
chunker = InsurancePolicyChunker(
    tokenizer=tokenizer,
    max_tokens=600,      # Increase for longer chunks
    min_chunk_tokens=150  # Increase to avoid tiny chunks
)
```

---

## Verification Checklist

Before deploying to production:

- [ ] ✅ Improved chunker copied to correct location
- [ ] ✅ build_index.py updated with new import and metadata
- [ ] ✅ Index rebuilt with new chunker
- [ ] ✅ Sample chunk verified to have new metadata fields
- [ ] ✅ Enhanced retrieval integrated
- [ ] ✅ Test queries produce better results than before
- [ ] ✅ LLM prompt updated to use structural metadata
- [ ] ✅ Logging added for monitoring
- [ ] ✅ Feedback mechanism in place

---

## Next Steps After Migration

1. **Fine-tune boost factors** based on real user queries
2. **Monitor edge cases** where retrieval still fails
3. **Consider adding a reranker** (CrossEncoder) for even better results
4. **Fine-tune your embedding model** on insurance policy text if possible
5. **Add query expansion** (e.g., "ACL" → "anterior cruciate ligament")

---

## Need Help?

If you run into issues, share:
1. The specific error message
2. A sample query that's failing
3. The top 3 chunks being retrieved
4. What you expected vs what you got

Good luck with the migration! 🚀