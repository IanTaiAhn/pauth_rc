# 🧱 MVP Tech Stack (Example)
* Backend: FastAPI
* NLP: Clinical NER + LLM classification
* Storage: Postgres
* Security: basic HIPAA hygiene
* UI: simple form + checklist view


# 1️⃣ High-Level Architecture (MVP) (View in edit mode)
[React Web App]
    |
    |  upload chart + select CPT + payer (optional)
    v
[FastAPI Backend]
    |
    |-- Document ingestion (PDF / text)
    |-- Evidence detection (LLM + rules)
    |-- Missing-info checklist
    |-- Justification assembly
    |
    v
[JSON PA Readiness Report]


### High-level Clarification
Chart Note (PDF / Text)
        |
        v
[1] Clinical Fact Extraction (NO RAG)
        |
        v
Structured Evidence JSON
(symptoms, duration, imaging, PT, etc.)
        |
        v
[2] Policy Criteria Retrieval (RAG)
(payer + CPT → criteria snippets)
        |
        v
[3] Criteria Matching
(evidence vs criteria checklist)
        |
        v
[4] Output Generation
- readiness
- missing items
- justification (uses RAG text)

### Clarifying how AI is used here.
| Layer                | What it Understands          | AI Model Role              |
| -------------------- | ---------------------------- | -------------------------- |
| **Clinical Reality** | What happened to the patient | **Qwen extracts facts**    |
| **Insurance Rules**  | What the payer requires      | **RAG retrieves criteria** |

### Iteration upon iteration.
Chart Note
   |
   v
[1] Evidence Extraction (Qwen, NO RAG)
   |   → Turns messy note into structured medical facts
   v
Structured Evidence JSON
   |
   v
[2] Policy Retrieval (RAG)
   |   → Fetches payer rules from your policy vector DB
   v
Policy Criteria Snippets
   |
   v
[3] Criteria Matching (Pure Logic)
   |   → Compares evidence JSON vs policy checklist
   v
Readiness Score + Missing Items
   |
   v
[4] Justification Generation (LLM + RAG text)
       → Uses evidence + retrieved policy language

### ⚙️ Important: RAG Is Only for Policies
### Do NOT put chart notes into this vector DB.

Your vector DB should ONLY contain:
* Payer medical policies
* Coverage determination documents
* Clinical criteria bullet lists
* If you mix charts in, you’ll get garbage retrieval.

### User's Perspective
1. Wrangle all the docs/pdfs/text files they can find and dump them into the evidence extraction code and create structured json object.
2. Once they have all that stuff they need to figure out which payer policy/criteria they're filling out for their patient.
3. Select the correct codes/policy/insurance company. (The indecies should already be built for them to use...)
4. They should receive a nice document with PA readiness check out of 100 with certain things highlighted and is usable.


#### Behind the scenes

* One-time setup (offline)
* Load policy PDFs
* Split into chunks (300–800 tokens)
* Embed chunks

Store in vector DB with metadata:
{
  "payer": "BCBS",
  "cpt_codes": ["62323", "64483"],
  "body_part": "lumbar_spine",
  "source": "BCBS_Lumbar_ESI_2025.pdf"
}

### FastAPI call
User uploads chart
        ↓
Qwen extracts facts
        ↓
You query RAG with payer + CPT (Transform it into Facts JSON for easy comparison)
        ↓
Vector DB returns matching policy rules
        ↓
Logic compares facts vs rules (deterministic rules coded by me)
        ↓
LLM writes justification using those rules

### Scalability?
Component	                Changes When?	        Needs Retraining?
Clinical extractor (Qwen)	Rarely	                ❌
Policy RAG DB	                Every policy update	✅ Just re-embed
Matching logic	                When rules change	❌
Justification writer	        Never	                ❌

#### Another Mental Model
Step	                Brain Used	        Data Source
Evidence extraction	Qwen	                Chart
Policy retrieval	Embeddings + Vector DB	Policy PDFs
Readiness scoring	Deterministic logic	Evidence + Policy
Justification writing	LLM	                Evidence + Policy text

### Api endpoints
/api/extract_policy_rules  [POST]   - Query RAG system
/api/build_index           [POST]   - Build new index
/api/delete_index/{name}   [DELETE] - Delete index
/api/list_indexes          [GET]    - List all indexes

/api/upload_document       [POST]   - Upload document
/api/list_uploaded_docs    [GET]    - List documents
/api/delete_uploaded_doc/  [DELETE] - Delete document

/api/analyze               [POST]   - Analyze PA document (NEW)

### Backend App Structure
backend/app/
├── main.py                 # Main app with all routers
├── routers/
│   ├── __init__.py
│   ├── rag.py             # RAG operations
│   ├── documents.py       # Document management
│   └── prior_auth.py      # PA analysis (NEW)
├── services/
│   ├── ingestion.py
│   ├── evidence.py
│   ├── readiness.py
│   └── justification.py
└── rag_pipeline/
    └── scripts/
        ├── ask_question.py
        └── build_index.py

### ChatGPT corrected workflow
Chart Note
   ↓
LLM → Evidence Extractor
   ↓
Structured Evidence JSON
   ↓
RAG → Policy Text
   ↓
LLM → Policy Rule Structurer
   ↓
Structured Rule JSON
   ↓
⚙️ Deterministic Logic Engine (NO LLM)
   ↓
Pass/Fail + Missing Items JSON
   ↓
LLM → Human-Readable Justification

### Claude Adjusted Workflow
Chart Note
   ↓
LLM → Evidence Extractor (with schema)
   ↓
Structured Evidence JSON (standardized medical entities)
   ↓
RAG Query (payer + CPT + diagnosis)
   ↓
Retrieved Policy Chunks (ranked by relevance)
   ↓
LLM → Policy Rule Parser (with strict schema + few-shot examples)
   ↓
Structured Criteria JSON (normalized conditions)
   ↓
⚙️ Schema Alignment Layer (map evidence fields to criteria fields)
   ↓
⚙️ Rules Engine (evaluates boolean logic)
   ↓
Authorization Decision + Evidence Gap Analysis
   ↓
LLM → Justification Generator (with templates)
   ↓
Human-Readable Letter


### ⚠️ Edge Cases to Plan For
* Ambiguous policy language - "reasonable trial of PT" - how does your structurer handle this?
* Missing evidence - Patient has no documented BMI. Fail or flag for human review?
* Conflicting rules - RAG returns contradictory policy versions
* Temporal logic - "Failed treatment for at least 90 days" requires date parsing
* Negative evidence - Proving something didn't happen (no contraindications documented)

### 🚀 Suggested MVP Scope
Start with:
* Single payer (fewer policy variations)
* 5-10 common CPT codes
* Simple boolean AND criteria only
* Manual rule authoring (not LLM-parsed) to validate the engine first
* Then progressively add the LLM policy parser once the engine works.


### Policy Criteria Rag Pipeline
Policy PDFs → Embeddings → Retrieval(uses specialized query to get relevant chunks) → Rerank → LLM Structuring(create another prompt using the reranked specialized chunks) → Policy Rules JSON
“I use semantic search to locate payer policy text, refine it with a relevance model, and then use an LLM to transform authoritative policy language into structured decision rules.”

Something I just thought of is that I only have to build indecies once, as well as the payer policy json.
The thing that actually has to get created a bunch is the extracted patient notes.

My source of truth that the RAG should be built on for maximum good retreival.

## So Where Should YOU Pull Policy Truth From?

If you want to mirror what reviewers actually use, your RAG sources should be:

### ✅ Primary
* State Medicaid provider manuals (PDFs)
* Medicaid PA instruction pages
* Medicaid imaging policy documents
* Coverage & reimbursement manuals

### ✅ Secondary
* Medicaid PA forms (what they ask for = what they care about)
* Denial reason descriptions
* Medicaid fee schedules with PA flags

### ⚠️ Avoid as primary truth
* Blog posts
* Revenue cycle vendor summaries
* Clinic “how-to” guides
* Those reflect interpretation, not enforcement.

Chart → Policy-derived checklist → Gap analysis → Submit once

Lol.
So we need to iterate again.
Chunking, retrieval, embedding, reranking...
This iteration round we target only Utah Medicaid.
### We must group based off of:
* Modality-based (MRI / CT / PET)
* Body-region–based (spine, brain, extremity)
* Indication-based (trauma, neuro deficit, cancer, pain > 6 weeks)
* Exception-based (red flags override conservative therapy rules)

My version initially was too naive. We are going to rebuild using actual pdfs from medicaid and get real source information.

## Level 1 — One Medicaid Imaging Policy Index
### This index contains:
* Provider manuals
* Imaging PA instructions
* Modality rules
* Conservative treatment requirements
* Red flag language
* Documentation expectations

## Level 2 — Chunk tagging (this is critical)
### Each chunk should be tagged with metadata like:
{
  "payer": "Utah Medicaid",
  "modality": "MRI",
  "body_region": "spine",
  "anatomic_area": "lumbar",
  "clinical_indication": ["pain", "radiculopathy"],
  "conservative_treatment_required": true,
  "red_flags": ["neurologic deficit", "trauma"],
  "source": "Provider Manual Section 3.2"
}

## Level 3 — CPT mapping layer (logic, not embeddings)
{
  "72148": {
    "modality": "MRI",
    "body_region": "spine",
    "anatomic_area": "lumbar",
    "contrast": "without"
  }
}

## Single Medicaid Imaging Index (Recommended)
## How your RAG pipeline should work (step-by-step)
### 🧱 Step 1: Source ingestion

### Ingest only documents reviewers would reference:
* Utah Medicaid provider manuals (PDF)
* Imaging PA instruction pages
* PA request forms
* Coverage & reimbursement criteria pages
* FAQ pages that describe requirements
* Normalize → clean → chunk semantically (not by page).

### 🧱 Step 2: Semantic chunking
Chunk by:
* Requirement type (conservative therapy, red flags, documentation)
* Modality
* Body region

* ❌ Don’t chunk by page
* ✅ Chunk by policy intent

### 🧱 Step 3: Metadata tagging

### Tag every chunk with:
* modality
* body_region
* anatomic_area
* condition keywords
* whether it’s a hard rule vs exception
* This is what lets you do targeted retrieval later.

### 🧱 Step 4: Patient chart extraction (json may need to be worked on)

### 🧱 Step 5: Policy matching
Now you:
* Query Medicaid Imaging Index using patient attributes
* Retrieve only relevant policy chunks
* Compare required elements vs extracted chart data
* Generate a gap report

### Pros
* Mirrors real reviewer logic
* Minimal duplication
* Easy to update
* Works across CPTs
* Faster iteration

### Cons
* Requires good metadata tagging
* Slightly more logic at query time

I need to change my structure to accept all MRI CPT things.

### Phase 1 (now)

### Support 5 MRI CPT families
* Knee
* Shoulder
* Lumbar spine
* Cervical spine
* Brain

* Single Medicaid Imaging Index
* Metadata + filters
* One prompt template

### Phase 2 (after first clinic)
* Add CT
* Add ultrasound
* Add contrast/no-contrast logic