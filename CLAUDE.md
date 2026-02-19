# P-Auth RC — Claude Code Context

## What This Application Does

P-Auth RC is a **prior authorization (PA) readiness checker** for healthcare imaging procedures. It automates the most time-consuming part of the PA workflow: determining whether a patient chart contains sufficient clinical evidence to satisfy a payer's coverage criteria before submitting the actual PA request.

The core loop:
1. A clinic uploads a patient chart note (PDF or TXT)
2. The system loads compiled rules and an extraction schema for the requested payer/CPT combination
3. An LLM extracts structured clinical facts from the chart using that schema — extracting exactly the fields the rules need, nothing more
4. A deterministic rule engine compares extracted patient evidence against the compiled policy rules
5. The system outputs a readiness score, gap analysis, and actionable report

**This is clinical decision support, not clinical decision automation.** A human clinician reviews and acts on the output.

---

## Business Context

**Target customers:** Small to mid-size orthopedic clinics, sports medicine clinics, and primary care practices that order imaging (MRI, CT).

**Initial scope:** Knee MRI CPT codes (73721, 73722, 73723) for Utah Medicaid. Expand by modality and payer after first paying customer.

**GTM positioning:** Decision support tool. Improves PA submission quality and reduces denials. Not a replacement for clinical judgment or a fully automated PA system.

**Revenue model:** SaaS subscription per clinic or per PA processed.

**Compliance posture:** The application handles real PHI and must be fully HIPAA-compliant before production. See the HIPAA section below for current status and the PHI boundary that governs all LLM provider decisions.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python), Uvicorn |
| LLM — PHI extraction (request time) | AWS Bedrock (Claude / Llama) — **BAA-required path; Groq is NOT acceptable here** |
| LLM — Policy Compiler (index-build time, no PHI) | Groq API / local Qwen2.5 — no BAA required, no PHI involved |
| Embeddings | SentenceTransformer (local MiniLM model) |
| Vector store | FAISS (flat inner-product index) + JSON metadata |
| Reranking | CrossEncoder (local MiniLM reranker) |
| Compiled rules store | JSON files on disk (`rag_pipeline/compiled_rules/`) |
| Data validation | Pydantic v2 |
| PDF ingestion | pdfplumber |
| Frontend | React + Vite (not yet implemented) |
| Python version | 3.11+ |

---

## The PHI Boundary — Read This Before Touching LLM Code

There are exactly **two LLM call sites** in this application. They have completely different compliance requirements:

```
┌─────────────────────────────────────────────────────────────┐
│  POLICY COMPILER  (index-build time)                        │
│  Input: policy document text — NO PHI                       │
│  Output: canonical_rules.json + extraction_schema.json      │
│  Provider: any LLM is acceptable (Groq, public APIs, etc.)  │
│  File: rag_pipeline/scripts/compile_policy.py               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PATIENT EXTRACTOR  (request time)                          │
│  Input: patient chart text — CONTAINS PHI                   │
│  Output: structured patient field values                    │
│  Provider: MUST be BAA-covered (AWS Bedrock)                │
│            Groq is NOT acceptable here                      │
│  File: services/evidence.py                                 │
└─────────────────────────────────────────────────────────────┘
```

**Never send patient chart text to Groq or any non-BAA provider.** If you are modifying `evidence.py` or any code that passes chart text to an LLM, the provider must be AWS Bedrock (or Azure OpenAI / GCP Vertex AI with a signed BAA). If you are modifying `compile_policy.py` or any code that processes policy documents, any provider is fine.

---

## Repository Structure

```
backend/
├── app/
│   ├── main.py                              # FastAPI app, CORS config
│   ├── routers/
│   │   ├── orchestration.py                 # POST /api/check_prior_auth (main endpoint)
│   │   ├── documents.py                     # Upload/list/delete policy docs
│   │   └── authz.py                         # POST /api/compare_json_objects (standalone eval)
│   ├── services/
│   │   ├── evidence.py                      # Schema-driven PHI extraction (Bedrock)
│   │   └── ingestion.py                     # File bytes → text
│   ├── rules/
│   │   └── rule_engine.py                   # Deterministic PA rule evaluation (NO LLM)
│   ├── rag_pipeline/
│   │   ├── compiled_rules/                  # OUTPUT of Policy Compiler — one JSON per payer/CPT
│   │   │   ├── utah_medicaid_73721.json      #   contains canonical_rules + extraction_schema
│   │   │   ├── utah_medicaid_73722.json
│   │   │   └── utah_medicaid_73723.json
│   │   ├── chunking/improved_chunker.py
│   │   ├── embeddings/embedder.py
│   │   ├── embeddings/vectorstore.py
│   │   ├── generation/generator.py          # MedicalGenerator: local | groq | bedrock
│   │   ├── generation/prompt.py
│   │   ├── retrieval/enhanced_retriever.py
│   │   ├── retrieval/enhanced_reranker.py
│   │   └── scripts/
│   │       ├── build_index_updated.py       # Step 1: build FAISS index (run once per policy doc)
│   │       ├── compile_policy.py            # Step 2: compile rules + schema (run once per policy doc)
│   │       └── extract_policy_rules.py      # RAG retrieval — used for exception guidance only
│   ├── data/patient_info/                   # SYNTHETIC test charts only — never real PHI
│   ├── api_models/schemas.py                # Pydantic request/response models
│   └── utils/
│       ├── make_report.py                   # Text report builder
│       └── save_json.py                     # JSON output utility
├── uploaded_docs/                           # Runtime policy document upload directory
└── requirements.txt

docs/
├── mvp.md
├── next_steps.md
├── project_structure.md
└── architecture_guide.md                   # Full policy-compiler architecture reference
```

### Files That No Longer Exist (Do Not Recreate)

- `normalization/normalized_custom.py` — deleted. Rules now come pre-compiled from `compile_policy.py`. There is no post-hoc normalization step.
- `routers/normalization.py` — deleted. Normalization endpoints are no longer needed.
- `routers/pa.py` and `routers/rag.py` — deleted. The single `/api/check_prior_auth` endpoint in `orchestration.py` replaces the separate extract/retrieve/compare flow.

---

## Key Architectural Decisions

**Why a Policy Compiler instead of runtime normalization?**
The old pipeline extracted a summary JSON from the policy (losing information), then re-parsed that summary into rules (losing more). The Policy Compiler reads the full policy document once at index-build time and produces a `canonical_rules.json` that the rule engine can evaluate directly — no intermediate re-interpretation. Adding a new CPT code requires running the compiler, not editing Python.

**Why schema-driven patient extraction?**
The old `evidence.py` used a hand-coded schema that had to be manually updated for every new CPT code and modality. The new approach derives the extraction schema from the compiled policy — the policy itself defines what fields the LLM should look for. The LLM extracts exactly the fields the rules need, nothing more.

**Why `count_gte` logic in the rule engine?**
Real payer policies use "at least 2 of the following" constructs (e.g., Utah Medicaid Section 2.4 conservative treatment). The old rule engine only supported `all` (AND) and `any` (OR), which could not express this correctly. The rule engine now supports `count_gte` and `count_lte` logic operators with a `threshold` field.

**Why are exception rules first-class objects in the rule set?**
The old architecture detected exceptions heuristically in orchestration.py. Exception rules are now part of the compiled rule set with explicit `overrides` arrays listing which standard rules they waive. This makes exception logic auditable and policy-document-driven rather than hard-coded.

**Why deterministic rule engine, not LLM for PA evaluation?**
Clinical accuracy and auditability require determinism. This is unchanged and non-negotiable. `rule_engine.py` is pure Python comparisons — no model involved.

**Why local models for embeddings and reranking?**
PHI must not leave the system unnecessarily. Embeddings and reranking run on local MiniLM models. RAG retrieval at request time is used only for exception guidance text, not for rule generation.

**Why FAISS over a managed vector DB?**
MVP simplicity. Known future migration point for production.

---

## Data Flow (End to End)

### Index-Build Time (runs once per policy document — no PHI)

```
Policy PDF/TXT
    ├──► build_index_updated.py — chunks text → FAISS index
    └──► compile_policy.py — reads full policy text
              │
              └──► LLM (any provider — no PHI)
                        │
                        ├──► canonical_rules.json   (evaluable rule objects)
                        └──► extraction_schema.json (patient fields to extract)
                   stored in rag_pipeline/compiled_rules/{payer}_{cpt}.json
```

### Request Time (runs per patient chart submission — PHI present)

```
Patient Chart (PDF/TXT)
    ↓
ingestion.py — bytes → text
    ↓
orchestration.py — loads compiled_rules/{payer}_{cpt}.json
    │
    ├──► extraction_schema → evidence.py
    │         LLM (AWS Bedrock — BAA required)
    │         extracts exactly the fields canonical_rules need
    │         → patient_data dict
    │
    └──► canonical_rules + patient_data → rule_engine.py
              deterministic evaluation
              → pass/fail per rule, score, gaps
    ↓
OrchestrationResponse — verdict, score, criteria, gaps, next_steps
```

---

## Compiled Rule Format

Every compiled rule set lives at `rag_pipeline/compiled_rules/{payer}_{cpt}.json`.

**Rule logic operators:**

| `logic` value | Meaning |
|---|---|
| `"all"` | All conditions must pass (AND) |
| `"any"` | At least one condition must pass (OR) |
| `"count_gte"` | At least `threshold` conditions must pass |
| `"count_lte"` | At most `threshold` conditions must pass |

**Rule flags:**

| Flag | Meaning |
|---|---|
| `"exception_pathway": true` | Rule is an exception. If it passes, rules in its `"overrides"` list are waived. |
| `"exclusion": true` | Rule is an exclusion. If the condition is NOT met, return EXCLUDED immediately without evaluating other rules. |

**Example — conservative treatment (count_gte):**
```json
{
  "id": "conservative_treatment",
  "description": "At least 2 of: PT≥6wks, NSAIDs≥4wks, activity mod, bracing, injection",
  "logic": "count_gte",
  "threshold": 2,
  "conditions": [
    { "field": "pt_duration_weeks",       "operator": "gte", "value": 6 },
    { "field": "nsaid_duration_weeks",    "operator": "gte", "value": 4 },
    { "field": "activity_mod_documented", "operator": "eq",  "value": true },
    { "field": "bracing_documented",      "operator": "eq",  "value": true },
    { "field": "injection_documented",    "operator": "eq",  "value": true }
  ]
}
```

**Example — exception rule:**
```json
{
  "id": "exception_red_flag",
  "description": "Red flag exception — waives conservative treatment",
  "logic": "any",
  "exception_pathway": true,
  "overrides": ["conservative_treatment"],
  "conditions": [
    { "field": "red_flag_infection_suspected", "operator": "eq", "value": true },
    { "field": "red_flag_tumor_suspected",     "operator": "eq", "value": true }
  ]
}
```

---

## Adding a New CPT Code or Payer

This requires **no Python changes**. The steps are:

```bash
# 1. Upload the policy document (existing endpoint)
POST /api/upload_document

# 2. Build the FAISS index
cd backend
python -c "from app.rag_pipeline.scripts.build_index_updated import build_index; build_index()"

# 3. Run the Policy Compiler (no PHI — any LLM provider is fine)
python -c "
from app.rag_pipeline.scripts.compile_policy import compile_policy
from pathlib import Path

text = Path('uploaded_docs/your_policy_file.txt').read_text()
compiled = compile_policy(text, payer='payer_id', cpt_code='73722')
print(f'{len(compiled[\"canonical_rules\"])} rules, {len(compiled[\"extraction_schema\"])} schema fields')
"

# 4. Add the entry to INDEX_MAP in orchestration.py
("payer_id", "73722"): "payer_id_73722",
```

Review the compiler output in `compiled_rules/payer_id_73722.json` before
deploying. The `_validation_errors` field in that file lists any structural
problems the compiler detected (missing fields, unknown operators, etc.).

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/check_prior_auth` | Full PA pipeline: ingest chart → extract → evaluate → respond |
| POST | `/api/upload_document` | Upload policy PDF/TXT for indexing |
| GET | `/api/list_uploaded_docs` | List uploaded documents |
| DELETE | `/api/delete_uploaded_doc/{filename}` | Delete a document |
| GET | `/api/list_indexes` | List available FAISS indexes |
| DELETE | `/api/delete_index/{name}` | Delete a FAISS index |
| GET | `/api/list_compiled_rules` | List available compiled rule sets |
| POST | `/api/compare_json_objects` | Standalone rule evaluation (dev/debug use) |

---

## HIPAA Compliance Status

**Current state: NOT production-ready for real PHI.**

### Open Issues

| ID | Severity | Status | Description |
|---|---|---|---|
| CRITICAL-1 | 🔴 CRITICAL | Open | No encryption at rest — files and FAISS store are plaintext |
| CRITICAL-2 | 🔴 CRITICAL | Open | CORS not environment-driven; misconfigured for production |
| CRITICAL-3 | 🔴 CRITICAL | Open | No authentication on any endpoint |
| CRITICAL-4 | 🔴 CRITICAL | Open | PHI sent to Groq without BAA — **fix: use Bedrock in `evidence.py` only; Groq remains in compiler** |
| CRITICAL-5 | 🔴 CRITICAL | Open | No audit logging of PHI access — stub exists in `evidence.py`, needs real implementation |
| HIGH-1 | 🟠 HIGH | Open | Hardcoded Windows path in `evidence.py` (`MODEL_PATH`) |
| HIGH-2 | 🟠 HIGH | Open | No HTTPS/TLS configuration |
| HIGH-3 | 🟠 HIGH | Open | No data retention policy |
| HIGH-4 | 🟠 HIGH | Open | Path traversal vulnerability in file upload |
| HIGH-5 | 🟠 HIGH | Open | No rate limiting |
| HIGH-6 | 🟠 HIGH | Open | Synthetic PHI-formatted test data in repo — needs pre-commit hook |
| MED-1 | 🟡 MED | Open | Tracebacks returned in HTTP error responses |
| MED-2 | 🟡 MED | Open | No secrets validation at startup |
| MED-3 | 🟡 MED | Open | No dependency vulnerability scanning |
| MED-4 | 🟡 MED | Open | Global mutable state (singletons in ASGI context) |
| MED-5 | 🟡 MED | Open | Pickle deserialization for FAISS metadata — replace with JSON |

### PHI Boundary Summary for LLM Provider Decisions

| Operation | PHI? | Acceptable providers |
|---|---|---|
| Policy Compiler (compile_policy.py) | No | Any — Groq, public APIs, local Qwen2.5 |
| Patient extraction (evidence.py) | **Yes** | AWS Bedrock, Azure OpenAI, GCP Vertex AI, local Qwen2.5 only |
| Embeddings (embedder.py) | No | Local MiniLM only (by design) |
| Reranking (enhanced_reranker.py) | No | Local MiniLM only (by design) |
| Rule evaluation (rule_engine.py) | Yes (in memory) | No external call — deterministic Python only |

### Compiled Rules — No PHI Risk

The `compiled_rules/` directory contains only policy-derived rule logic and field
definitions. It contains zero patient data and zero PHI. These files can be stored
in version control, shared freely, and backed up without HIPAA considerations. Policy
version changes are auditable as git diffs.

---

## Development Conventions

### Running the backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### Environment variables required
```
GROQ_API_KEY=             # For Policy Compiler only (no PHI)
AWS_REGION=               # For Bedrock patient extraction
AWS_ACCESS_KEY_ID=        # For Bedrock (or use IAM role in production)
AWS_SECRET_ACCESS_KEY=    # For Bedrock (or use IAM role in production)
BEDROCK_MODEL_ID=         # e.g. anthropic.claude-sonnet-4-6
SENT_TRANSFORMER_MODEL=   # Path to local MiniLM model
VECTOR_STORE_PATH=        # Path to FAISS index directory
MODEL_PATH=               # Path to local Qwen2.5 (fallback only)
```

### Full index-build workflow (one-time per policy document)
```bash
cd backend

# Step 1: Build FAISS index
python -c "from app.rag_pipeline.scripts.build_index_updated import build_index; build_index()"

# Step 2: Compile rules and extraction schema
python -c "
from app.rag_pipeline.scripts.compile_policy import compile_policy
from pathlib import Path
text = Path('uploaded_docs/your_policy.txt').read_text()
compile_policy(text, payer='utah_medicaid', cpt_code='73721')
"
```

### Running tests
```bash
cd backend
python app/tests/tests_custom.py
```

### Code style rules
- All paths must use `pathlib.Path` or environment variables — **never hardcode absolute paths**
- Never return exception tracebacks to HTTP clients — log server-side only
- Patient chart text must never be passed to Groq or any non-BAA provider — use `provider="bedrock"` in `evidence.py`
- New API endpoints follow existing router pattern: `APIRouter` + Pydantic request/response models
- `rule_engine.py` must remain LLM-free — non-negotiable
- New rule logic operators (`count_gte`, `count_lte`) belong in `rule_engine.py` only — not in the compiler or orchestration layer
- Compiled rule files are the source of truth for what gets evaluated — do not add one-off rule logic in orchestration.py

### Test data
Files in `backend/app/data/patient_info/` are **synthetic test data only**. They must be clearly marked as such. Never commit real patient data. The 10 diagnostic artifacts in `api_artifacts/` are the validation ground truth for the pipeline — any change to the rule engine or compiler output should be checked against them.

---

## Product Roadmap Context

**Phase 1 (current):** Utah Medicaid, knee MRI (CPT 73721/22/23). Prove the compiled-rules pipeline end to end. Resolve CRITICAL HIPAA items before any real charts are processed.

**Phase 2:** Add MRI families (shoulder 73221, lumbar spine 72148, cervical spine 72141, brain 70553). Each is a compiler run + index build — no Python changes. Validate compiler output against known policy criteria before deploying each new CPT.

**Phase 3:** Multi-payer. Aetna as second payer. The compiler prompt is payer-agnostic — the same workflow applies.

**Longer term:** Real-time policy update detection, EHR integration, appeal letter generation using RAG over policy exception text.

**What we are NOT building:** A fully automated PA submission system. Human review is always in the loop.

---

## Guides (Read On Demand)

- **Full policy-compiler architecture, migration plan, HIPAA detail** → `docs/architecture_guide.md`
- **Business strategy, target customers** → `docs/next_steps.md`

Do not load these at session start. Read only when the conversation requires it.
