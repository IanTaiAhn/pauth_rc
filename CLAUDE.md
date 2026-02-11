# P-Auth RC — Claude Code Context

## What This Application Does

P-Auth RC is a **prior authorization (PA) readiness checker** for healthcare imaging procedures. It automates the most time-consuming part of the PA workflow: determining whether a patient chart contains sufficient clinical evidence to satisfy a payer's (insurance company's) coverage criteria before submitting the actual PA request.

The core loop:
1. A clinic uploads a patient chart note (PDF or TXT)
2. An LLM extracts structured clinical facts from the note (diagnoses, treatments, imaging, duration, etc.)
3. A RAG pipeline retrieves the relevant payer policy criteria for the requested CPT code
4. A deterministic rule engine compares patient evidence against policy requirements
5. The system outputs a readiness score, gap analysis, and actionable report

**This is clinical decision support, not clinical decision automation.** A human clinician reviews and acts on the output. The system is a tool — like a drill instead of a screwdriver.

---

## Business Context

**Target customers:** Small to mid-size orthopedic clinics, sports medicine clinics, and primary care practices that order imaging (MRI, CT). These clinics feel the pain of PA denials before radiology does.

**Initial scope:** Knee MRI CPT codes (73721, 73722, 73723) for Aetna. Expand by modality and payer after first paying customer.

**GTM positioning:** Decision support tool. Improves PA submission quality and reduces denials. Not a replacement for clinical judgment or a fully automated PA system.

**Revenue model:** SaaS subscription per clinic or per PA processed.

**Compliance posture:** The application handles real PHI (Protected Health Information) and must be fully HIPAA-compliant before production. We are building toward that. See the HIPAA section below.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python), Uvicorn |
| LLM — PHI extraction | Groq API (llama-3.3-70b-versatile) — **temporary, must be replaced with HIPAA-eligible provider before production** |
| LLM — policy extraction | Groq API / local Qwen2.5 |
| Embeddings | SentenceTransformer (local MiniLM model) |
| Vector store | FAISS (flat inner-product index) + pickle metadata |
| Reranking | CrossEncoder (local MiniLM reranker) |
| Data validation | Pydantic v2 |
| PDF ingestion | pdfplumber |
| Frontend | React + Vite (Not implemented yet) |
| Python version | 3.11+ (uses `tuple[bool, list]` syntax) |

---

## Repository Structure

```
backend/
├── app/
│   ├── main.py                        # FastAPI app, CORS config
│   ├── routers/
│   │   ├── pa.py                      # POST /api/extract_patient_chart
│   │   ├── rag.py                     # POST /api/extract_policy_rules
│   │   ├── documents.py               # Upload/list/delete docs
│   │   ├── authz.py                   # POST /api/compare_json_objects (PA evaluation)
│   │   └── normalization.py           # Normalize patient/policy JSON
│   ├── services/
│   │   ├── evidence.py                # LLM-based PHI extraction (EvidenceExtractor class)
│   │   ├── ingestion.py               # File bytes → text
│   │   └── readiness.py               # Readiness score computation
│   ├── normalization/
│   │   └── normalized_custom.py       # Patient + policy JSON normalization
│   ├── rules/
│   │   └── rule_engine.py             # Deterministic PA rule evaluation (NO LLM)
│   ├── rag_pipeline/
│   │   ├── chunking/improved_chunker.py
│   │   ├── embeddings/embedder.py + vectorstore.py
│   │   ├── generation/generator.py + prompt.py
│   │   ├── retrieval/enhanced_retriever.py + enhanced_reranker.py
│   │   └── scripts/
│   │       ├── build_index_updated.py  # Index builder (run once per policy doc)
│   │       └── extract_policy_rules.py # Full RAG → LLM → structured rules pipeline
│   ├── data/patient_info/             # SYNTHETIC test charts only
│   ├── api_models/schemas.py          # Pydantic request/response models
│   └── utils/
│       ├── make_report.py             # Text report builder
│       └── save_json.py               # JSON output utility
├── uploaded_docs/                     # Runtime document upload directory
└── requirements.txt
docs/
├── mvp.md                             # Architecture decisions and MVP scope
├── next_steps.md                      # Business and product roadmap
└── project_structure.md               # Detailed architecture notes
```

---

## Key Architectural Decisions

**Why deterministic rule engine, not LLM for PA evaluation?**
Clinical accuracy and auditability require determinism. An LLM-based comparison would be unpredictable and unauditable. The rule engine (`rule_engine.py`) is pure Python comparisons — no model involved. This is intentional and should not change.

**Why local models for embeddings and reranking?**
PHI must not leave the system unnecessarily. Embeddings and reranking run on local MiniLM models. The only external API calls are for LLM text generation.

**Why FAISS over a vector database service?**
MVP simplicity. FAISS runs in-process with no external dependencies. This is a known future migration point — a managed vector DB (Pinecone, Weaviate, pgvector) would be more production-appropriate.

**Why RAG for policy retrieval?**
Insurance policies are long, structured documents that change regularly. RAG lets us update policies by re-indexing without retraining. Policy indexes are built once per document and reused across all patient evaluations.

**Two-format patient JSON normalization:**
`normalize_patient_evidence()` handles both raw Groq LLM output (Format 1) and pre-normalized data (Format 2). This was intentional to support different ingestion paths without breaking the evaluation pipeline.

---

## Data Flow (End to End)

```
Patient Chart (PDF/TXT)
    ↓
ingestion.py — bytes → text
    ↓
evidence.py — LLM extracts structured clinical facts → patient_chart.json
    ↓
normalization/normalized_custom.py — flatten to canonical fields
    ↓
                    ← rag pipeline: policy doc → FAISS index → extract_policy_rules.py
                         → normalized policy rules
    ↓
rule_engine.py — deterministic comparison → pass/fail per rule
    ↓
make_report.py — human-readable PA readiness report
```

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/extract_patient_chart` | Upload chart, extract PHI + clinical evidence |
| POST | `/api/extract_policy_rules` | RAG pipeline → structured payer rules |
| POST | `/api/compare_json_objects` | Evaluate patient evidence vs policy rules |
| POST | `/api/compare_json_objects/report` | Same as above + returns downloadable report |
| POST | `/api/normalize/patient` | Normalize patient JSON only |
| POST | `/api/normalize/policy` | Normalize policy JSON only |
| POST | `/api/upload_document` | Upload policy PDF/TXT for indexing |
| GET | `/api/list_uploaded_docs` | List uploaded documents |
| DELETE | `/api/delete_uploaded_doc/{filename}` | Delete a document |
| GET | `/api/list_indexes` | List available FAISS indexes |
| DELETE | `/api/delete_index/{name}` | Delete a FAISS index |

---

## HIPAA Compliance Status

**Current state: NOT production-ready for real PHI.**

This application processes PHI (patient names, DOBs, MRNs, diagnoses, insurance IDs). The following compliance work is in progress and must be completed before any live patient data is used.

### Open HIPAA Issues (tracked in GitHub)

| ID | Severity | Status | Description |
|---|---|---|---|
| CRITICAL-1 | 🔴 CRITICAL | Open | No encryption at rest — files and FAISS store are plaintext |
| CRITICAL-2 | 🔴 CRITICAL | Open | CORS not environment-driven; misconfigured for production |
| CRITICAL-3 | 🔴 CRITICAL | Open | No authentication on any endpoint |
| CRITICAL-4 | 🔴 CRITICAL | Open | PHI sent to Groq without confirmed BAA |
| CRITICAL-5 | 🔴 CRITICAL | Open | No audit logging of PHI access |
| HIGH-1 | 🟠 HIGH | Open | Hardcoded Windows paths in evidence.py |
| HIGH-2 | 🟠 HIGH | Open | No HTTPS/TLS configuration |
| HIGH-3 | 🟠 HIGH | Open | No data retention policy |
| HIGH-4 | 🟠 HIGH | Open | Path traversal vulnerability in file upload |
| HIGH-5 | 🟠 HIGH | Open | No rate limiting |
| HIGH-6 | 🟠 HIGH | Open | Mocked PHI-formatted test data in repo |
| MED-1 | 🟡 MED | Open | Tracebacks returned in HTTP error responses |
| MED-2 | 🟡 MED | Open | No secrets validation at startup |
| MED-3 | 🟡 MED | Open | No dependency vulnerability scanning |
| MED-4 | 🟡 MED | Open | Global mutable state (singletons in ASGI context) |
| MED-5 | 🟡 MED | Open | Pickle deserialization for FAISS metadata |

### HIPAA-Eligible LLM Provider Plan

Groq must be replaced before production. Preferred path: **AWS Bedrock** (supports Claude, Llama; HIPAA BAA available). Azure OpenAI and GCP Vertex AI are also acceptable. The local Qwen2.5 model is an acceptable fallback for environments where no external LLM calls are permissible.

The `EvidenceExtractor` class in `evidence.py` and `MedicalGenerator` in `generator.py` are designed for this swap — they accept a `provider` parameter. The migration requires updating these classes to support a new provider and confirming a signed BAA.

### What Is Already Good

- Hallucination detection (`_validate_evidence()`) cross-checks extracted notes against source text
- Deterministic rule engine with no LLM — auditable and consistent
- Pydantic validation on all inputs/outputs
- Local model option that never transmits PHI externally
- Clean service/router separation that makes adding auth middleware straightforward

---

## Development Conventions

### Running the backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### Environment variables required
```
GROQ_API_KEY=           # LLM API key (Groq or future provider)
SENT_TRANSFORMER_MODEL= # Path to local MiniLM model (default: app/rag_pipeline/models/minilm)
VECTOR_STORE_PATH=      # Path to FAISS index directory (default: app/rag_pipeline/vectorstore)
MODEL_PATH=             # Path to local Qwen2.5 model
```

### Building a policy index (one-time per document)
```bash
cd backend
python -c "from app.rag_pipeline.scripts.build_index_updated import build_index; build_index()"
```

### Running tests
```bash
cd backend
python app/tests/tests_custom.py
```

### Code style rules
- All paths must use `pathlib.Path` or environment variables — **never hardcode absolute paths**
- Never return exception tracebacks to HTTP clients — log server-side only
- All PHI-touching endpoints will require authentication (being added — see CRITICAL-3)
- New API endpoints follow existing router pattern: `APIRouter` + Pydantic request/response models
- The rule engine (`rule_engine.py`) must remain LLM-free — this is non-negotiable

### Test data
Files in `backend/app/data/patient_info/` are **synthetic test data only**. They must be clearly marked as such. Never commit real patient data to this repository under any circumstances. A pre-commit hook for PHI detection should be added (see HIGH-6).

---

## Product Roadmap Context

**Phase 1 (current):** Single payer (Aetna), single modality (knee MRI, CPT 73721/22/23). Prove the pipeline works end to end.

**Phase 2:** Add more MRI families (shoulder, lumbar spine, cervical spine, brain). Single Medicaid imaging index with metadata filtering.

**Phase 3:** Multi-payer support. Utah Medicaid as second payer target. Add CT and ultrasound modalities.

**Longer term:** Real-time payer policy updates, clinic EHR integration, appeal letter generation.

**What we are NOT building:** A fully automated PA submission system. This is always decision support with a human in the loop.

---

## Guides (Read On Demand)

If the conversation touches these topics, relevant detail is in these files:

- **Architecture decisions, MVP scope, RAG design** → `docs/mvp.md`
- **Business strategy, target customers, sales approach** → `docs/next_steps.md`
- **Full project structure, API design rationale** → `docs/project_structure.md`
- **Normalization module details** → `backend/app/normalization/README.md`

Do not load these at session start. Read only when the conversation requires it.
