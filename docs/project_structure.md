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

TODO, need and upload and results page.

# 2️⃣ Backend Skeleton (FastAPI)
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── pa.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   ├── models/
│   │   ├── pa_models.py
│   ├── services/
│   │   ├── ingestion.py
│   │   ├── evidence.py
│   │   ├── readiness.py
│   │   ├── justification.py
│   ├── utils/
│   │   ├── text.py
│   └── requirements.py

## Next Steps
### Step 1: Start with .txt uploads

Keep ingestion simple.

### Step 2: Normalize text

Run everything through normalize_text().

### Step 3: Run evidence detectors

Check:
* conservative therapy
* duration
* failed treatments
* severity
* imaging

### Step 4: Validate outputs manually

Ask:
“Does this checklist match what a clinic would expect?”

If yes — you’re on the right track.


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
You query RAG with payer + CPT
        ↓
Vector DB returns matching policy rules
        ↓
Logic compares facts vs rules
        ↓
LLM writes justification using those rules

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
/api/ask_question          [POST]   - Query RAG system
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