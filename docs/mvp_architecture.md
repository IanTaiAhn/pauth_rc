# P-Auth RC MVP: Policy-to-Checklist Architecture

## The Product in One Sentence

A web app where clinic staff select a payer + CPT code and get a downloadable, fillable PDF checklist of exactly what documentation is required for PA approval — with plain-English explanations, ICD-10 code lookups, and denial-prevention tips.

**No PHI enters the system. No HIPAA infrastructure required. No patient data, ever.**

---

## What Changed and Why

### Previous Architecture (Full PA Readiness Checker)

```
Patient Chart (PDF) → LLM extraction → rule engine → readiness verdict
```

**Problems:** Requires HIPAA compliance, BAA with AWS, encryption at rest, audit logging, authentication — all before a single customer. Chart extraction accuracy is unreliable on real clinical notes. Chicken-and-egg: need patient data to validate, need HIPAA to handle patient data.

### New MVP Architecture (Policy Criteria Lookup + Fillable Checklist)

```
Policy PDF → LLM compiler → human-curated rules → web app serves checklist
Clinician downloads PDF → fills it out locally with patient info → never touches our servers
```

**What this eliminates:**
- All HIPAA critical issues (CRITICAL-1 through CRITICAL-5)
- AWS Bedrock dependency and BAA requirement
- Patient chart extraction (evidence.py, entire extraction pipeline)
- PHI boundary management
- Encryption at rest, audit logging, authentication (for MVP)

**What this preserves from existing work:**
- Policy Compiler (`compile_policy.py`) — still generates rule drafts from policy PDFs
- Field Registry (`knee_mri.registry.json`) — still defines canonical field vocabulary
- Rule validation (`validate_rules.py`) — still catches structural errors
- Rule engine logic concepts (`count_gte`, exceptions, exclusions) — informs checklist structure
- Compiled rules format — drives checklist generation

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  BUILD TIME  (you, the developer — runs once per payer/CPT)     │
│                                                                  │
│  Real Policy PDF (e.g., EviCore MSK Imaging Guidelines)          │
│       │                                                          │
│       └──► Policy Compiler (LLM, any provider — no PHI)          │
│               │                                                  │
│               └──► draft_rules.json (LLM output, needs review)   │
│                        │                                         │
│               ┌────────┘                                         │
│               ▼                                                  │
│       Human Review + Curation                                    │
│               │                                                  │
│               ├──► {payer}_{cpt}.rules.json (canonical, frozen)  │
│               ├──► {domain}.registry.json (field definitions)    │
│               └──► validate_rules.py confirms structural health  │
│                                                                  │
│       All stored in version control. No PHI. No secrets.         │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  SERVE TIME  (web app — serves checklists to clinic staff)       │
│                                                                  │
│  Clinic user visits app:                                         │
│       │                                                          │
│       ├──► Selects Payer (dropdown)                              │
│       ├──► Selects Procedure / CPT Code (dropdown)               │
│       │                                                          │
│       ▼                                                          │
│  App loads {payer}_{cpt}.rules.json from static store            │
│       │                                                          │
│       ├──► Renders interactive checklist in browser               │
│       │      - Requirements grouped by section                   │
│       │      - Plain-English explanations per item               │
│       │      - Accepted ICD-10 codes with descriptions           │
│       │      - Exception pathways highlighted                    │
│       │      - Common denial reasons flagged                     │
│       │                                                          │
│       └──► "Download PDF Checklist" button                       │
│              Generates fillable PDF on the fly                   │
│              Clinician fills it out locally (Adobe, Preview)     │
│              PHI never leaves their machine                      │
│                                                                  │
│  NO patient data enters the system. Ever.                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## What You're Reusing vs. Building vs. Deleting

### REUSE (already built, still valuable)

| Asset | Location | Role in MVP |
|-------|----------|-------------|
| Policy Compiler | `compile_policy.py` | Generates draft rules from real policy PDFs (EviCore, Aetna CPBs) |
| Field Registry | `knee_mri.registry.json` | Canonical field names, types, descriptions — drives checklist labels |
| Rule Validation | `validate_rules.py` | Validates structural integrity of curated rule files |
| Rule Format | `utah_medicaid_73721.rules.json` | Template for all new payer/CPT rule files |
| Rule Engine Concepts | `rule_engine.py` logic | `count_gte`, `any`, `all`, exceptions, exclusions — inform checklist structure |
| Compiler Prompt | `COMPILER_SYSTEM_PROMPT` | Reuse for processing real EviCore/Aetna policies |

### BUILD (new for MVP)

| Component | Purpose | Effort |
|-----------|---------|--------|
| React frontend | Payer/CPT selector, interactive checklist view, ICD-10 search | 1-2 weeks |
| PDF generator | Converts rules.json → fillable PDF checklist | 2-3 days |
| Checklist transformer | Converts rules.json → human-readable checklist data | 1-2 days |
| Static API | FastAPI serves rule files + checklist data (no DB needed) | 1 day |
| ICD-10 lookup module | Searchable ICD-10 code database with plain-English descriptions | 1-2 days |
| Real policy rule files | Curate rules from EviCore MSK Imaging Guidelines (knee section) | 3-5 days |

### DELETE (no longer needed for MVP)

| Component | Reason |
|-----------|--------|
| `evidence.py` (patient extraction) | No patient data in MVP |
| `ingestion.py` (PDF text extraction for charts) | No chart upload |
| Bedrock integration | No PHI = no BAA needed |
| FAISS index + embeddings pipeline | No RAG retrieval needed |
| `enhanced_retriever.py`, `enhanced_reranker.py` | No retrieval pipeline |
| `build_index_updated.py` | No index building |
| All HIPAA compliance items | No PHI = not applicable |
| `orchestration.py` (full PA pipeline) | Replaced by static checklist serving |

**Don't actually delete these files** — move them to a `v2/` or `deferred/` directory. They're the foundation of the Phase 2 product (optional chart upload with LLM pre-fill).

---

## Detailed Component Design

### 1. Curated Rules Store (Static JSON Files)

This is the core of the product. Each file represents one payer + CPT combination.

```
rules/
├── evicore_73721.rules.json         # EviCore (Aetna, Cigna) — knee MRI no contrast
├── evicore_73722.rules.json         # EviCore — knee MRI with contrast
├── evicore_73723.rules.json         # EviCore — knee MRI without and with contrast
├── aetna_cpb0171_73721.rules.json   # Aetna CPB (if different from EviCore)
├── utah_medicaid_73721.rules.json   # Utah Medicaid — knee MRI no contrast
│
├── registries/
│   ├── knee_mri.registry.json       # Domain field definitions
│   └── shoulder_mri.registry.json   # (future)
│
└── metadata/
    └── payer_cpt_index.json         # Master index of all available combinations
```

**The rules.json format evolves slightly for the checklist use case.** Add human-facing fields:

```json
{
  "payer": "EviCore (Aetna, Cigna, and others)",
  "payer_id": "evicore",
  "cpt_code": "73721",
  "cpt_description": "MRI, any joint of lower extremity, without contrast",
  "policy_source": "EviCore MSK Imaging Guidelines V1.0.2025, Section MS-25",
  "policy_effective_date": "2025-02-01",
  "last_curated": "2026-02-20",
  "curator_notes": "Compiled from EviCore guidelines, reviewed against Aetna CPB #0171",

  "checklist_sections": [
    {
      "id": "eligible_diagnosis",
      "title": "Eligible Diagnosis",
      "description": "The patient must have a documented diagnosis that qualifies for knee MRI",
      "requirement_type": "any",
      "help_text": "At least ONE of the following must be documented in the chart",
      "items": [
        {
          "field": "meniscal_tear_suspected",
          "label": "Suspected meniscal tear",
          "help_text": "Document the clinical basis: positive McMurray's, joint line tenderness with mechanical symptoms, or history of twisting injury with locking/catching",
          "icd10_codes": ["M23.200", "M23.201", "M23.202", "M23.209", "M23.300"],
          "input_type": "checkbox"
        },
        {
          "field": "ligament_injury_suspected",
          "label": "Suspected ligamentous injury (partial or complete)",
          "help_text": "Document exam findings: positive Lachman, anterior/posterior drawer, or varus/valgus instability",
          "icd10_codes": ["S83.501A", "S83.511A", "S83.521A"],
          "input_type": "checkbox"
        }
      ]
    },

    {
      "id": "clinical_findings",
      "title": "Clinical Examination Findings",
      "description": "At least one positive clinical finding must be documented from a recent exam",
      "requirement_type": "any",
      "help_text": "Document at least ONE positive finding within 30 days of the PA request",
      "items": [
        {
          "field": "mcmurray_positive",
          "label": "Positive McMurray's test",
          "help_text": "Must be explicitly documented as positive (not equivocal or deferred)",
          "input_type": "checkbox"
        },
        {
          "field": "joint_line_tenderness",
          "label": "Joint line tenderness with mechanical symptoms",
          "help_text": "Document location (medial/lateral) and associated mechanical symptoms (clicking, locking, catching)",
          "input_type": "checkbox"
        }
      ]
    },

    {
      "id": "prior_imaging",
      "title": "Prior Imaging",
      "description": "Weight-bearing X-rays must be completed before MRI can be authorized",
      "requirement_type": "all",
      "help_text": "ALL of the following must be met",
      "items": [
        {
          "field": "xray_completed",
          "label": "X-rays of the affected knee completed",
          "input_type": "checkbox"
        },
        {
          "field": "xray_date",
          "label": "Date of X-rays",
          "help_text": "Must be within 60 days of the PA request",
          "input_type": "date",
          "validation": { "max_days_ago": 60 }
        },
        {
          "field": "xray_weightbearing",
          "label": "X-rays were weight-bearing views",
          "help_text": "Non-weight-bearing views may not satisfy this requirement. If the patient cannot bear weight, document the reason.",
          "input_type": "checkbox"
        }
      ]
    },

    {
      "id": "conservative_treatment",
      "title": "Conservative Treatment",
      "description": "At least 2 treatment modalities must be documented over a minimum period",
      "requirement_type": "count_gte",
      "threshold": 2,
      "help_text": "Document at least 2 of the following 5 treatments. Include dates, duration, and outcome.",
      "items": [
        {
          "field": "pt_completed",
          "label": "Physical therapy (≥6 weeks)",
          "help_text": "Include: start date, frequency, total duration, and outcome. Must be at least 6 weeks.",
          "input_type": "checkbox_with_detail",
          "detail_fields": [
            { "field": "pt_start_date", "label": "PT start date", "input_type": "date" },
            { "field": "pt_weeks", "label": "Total weeks", "input_type": "number" },
            { "field": "pt_frequency", "label": "Frequency (e.g., 2x/week)", "input_type": "text" }
          ]
        },
        {
          "field": "nsaid_trial",
          "label": "NSAIDs or oral analgesics (≥4 weeks)",
          "help_text": "Document: medication name, dose, duration, and reason for discontinuation if applicable",
          "input_type": "checkbox_with_detail",
          "detail_fields": [
            { "field": "nsaid_name", "label": "Medication", "input_type": "text" },
            { "field": "nsaid_weeks", "label": "Duration (weeks)", "input_type": "number" }
          ]
        },
        {
          "field": "activity_modification",
          "label": "Activity modification",
          "help_text": "Document specific restrictions: weight-bearing limits, activity avoidance, work modifications",
          "input_type": "checkbox"
        },
        {
          "field": "bracing",
          "label": "Bracing, orthotics, or assistive devices",
          "help_text": "Document type of device and duration of use",
          "input_type": "checkbox"
        },
        {
          "field": "injection",
          "label": "Intra-articular injection",
          "help_text": "Document: injection type (corticosteroid, hyaluronic acid), date, and response",
          "input_type": "checkbox"
        }
      ]
    },

    {
      "id": "notes_recency",
      "title": "Clinical Notes Recency",
      "description": "Clinical documentation must be current",
      "requirement_type": "all",
      "help_text": "The chart note supporting this PA request must be within 30 days",
      "items": [
        {
          "field": "notes_date",
          "label": "Date of supporting clinical note",
          "help_text": "Must be within 30 days of PA submission date",
          "input_type": "date",
          "validation": { "max_days_ago": 30 }
        }
      ]
    }
  ],

  "exception_pathways": [
    {
      "id": "exception_acute_trauma",
      "title": "Acute Trauma Exception",
      "description": "Waives conservative treatment requirement",
      "waives": ["conservative_treatment"],
      "help_text": "If 2 or more of the following are present, conservative treatment is NOT required",
      "requirement_type": "count_gte",
      "threshold": 2,
      "items": [
        {
          "field": "unable_to_bear_weight",
          "label": "Patient unable to bear weight at evaluation",
          "input_type": "checkbox"
        },
        {
          "field": "suspected_complete_rupture",
          "label": "Suspected complete ligament rupture",
          "input_type": "checkbox"
        },
        {
          "field": "locked_knee",
          "label": "Locked knee (unable to fully extend)",
          "input_type": "checkbox"
        }
      ]
    },
    {
      "id": "exception_red_flag",
      "title": "Red Flag Exception",
      "description": "Waives conservative treatment for suspected serious pathology",
      "waives": ["conservative_treatment"],
      "help_text": "If ANY of the following is present, conservative treatment is NOT required. Provide supporting documentation.",
      "requirement_type": "any",
      "items": [
        {
          "field": "suspected_infection",
          "label": "Suspected joint infection (fever, elevated inflammatory markers, turbid aspirate)",
          "input_type": "checkbox"
        },
        {
          "field": "suspected_tumor",
          "label": "Suspected bone or soft tissue tumor",
          "input_type": "checkbox"
        },
        {
          "field": "suspected_fracture",
          "label": "Suspected occult fracture (high suspicion with negative X-ray)",
          "input_type": "checkbox"
        }
      ]
    },
    {
      "id": "exception_postop",
      "title": "Post-Operative Exception",
      "description": "Waives conservative treatment for recent surgical patients",
      "waives": ["conservative_treatment"],
      "help_text": "If the patient had knee surgery within the past 6 months, conservative treatment is NOT required",
      "requirement_type": "all",
      "items": [
        {
          "field": "postop_within_6_months",
          "label": "Knee surgery within past 6 months",
          "input_type": "checkbox_with_detail",
          "detail_fields": [
            { "field": "surgery_date", "label": "Surgery date", "input_type": "date" },
            { "field": "surgery_type", "label": "Procedure", "input_type": "text" }
          ]
        }
      ]
    }
  ],

  "exclusions": [
    {
      "id": "exclusion_workers_comp",
      "title": "Workers' Compensation",
      "description": "Workers' comp cases are NOT covered under Medicaid — bill the WC carrier",
      "severity": "hard_stop"
    },
    {
      "id": "exclusion_screening",
      "title": "Routine Screening Without Symptoms",
      "description": "MRI for asymptomatic screening without clinical indication is not covered",
      "severity": "hard_stop"
    }
  ],

  "denial_prevention_tips": [
    "Anterior knee pain alone (without mechanical symptoms) → automatic denial. Document locking, catching, or giving-way if present.",
    "Repeat MRI within 12 months → requires documented change in clinical status since prior imaging.",
    "'Knee pain' as the sole diagnosis is insufficient. Specify the suspected pathology (meniscal tear, ligament injury, etc.).",
    "Equivocal exam findings (e.g., 'McMurray's equivocal') do NOT satisfy the clinical findings requirement. Re-examine and document clearly.",
    "Conservative treatment dates and durations must be explicit. 'Patient tried PT' without dates/duration will be denied."
  ],

  "submission_reminders": [
    "Authorization is valid for 60 calendar days from approval.",
    "Include: order with CPT code, clinical notes, X-ray report, and this completed checklist.",
    "Standard PA decision timeline: 7 calendar days. Urgent: 72 hours."
  ]
}
```

### 2. Checklist-to-PDF Generator

Reads a `rules.json` file and produces a fillable PDF the clinician can download and complete locally.

```
rules.json → checklist_pdf_generator.py → fillable_checklist.pdf
```

**PDF structure:**

```
┌──────────────────────────────────────────────┐
│  PRIOR AUTHORIZATION CHECKLIST               │
│  Payer: EviCore (Aetna/Cigna)                │
│  Procedure: MRI Knee Without Contrast (73721)│
│  Policy: EviCore MSK V1.0.2025, MS-25        │
│  Generated: 2026-02-20                       │
├──────────────────────────────────────────────┤
│                                              │
│  Patient Name: ___________________________   │
│  DOB: ___________  MRN: _________________   │
│  Date of Service: ________________________   │
│  Ordering Provider: ______________________   │
│                                              │
├──────────────────────────────────────────────┤
│  ⬚ STOP: Is this a Workers' Comp case?      │
│    If YES → Do not submit to Medicaid.       │
│    Bill the WC carrier directly.             │
│                                              │
├──────────────────────────────────────────────┤
│  SECTION 1: ELIGIBLE DIAGNOSIS               │
│  (Check at least ONE)                        │
│                                              │
│  ☐ Suspected meniscal tear                   │
│    ICD-10: M23.200, M23.201, M23.202...     │
│  ☐ Suspected ligamentous injury              │
│    ICD-10: S83.501A, S83.511A...            │
│  ☐ Osteochondral defect                      │
│  ☐ Mechanical symptoms (locking/catching)    │
│                                              │
│  ICD-10 Code Used: ______________________   │
│                                              │
├──────────────────────────────────────────────┤
│  SECTION 2: CLINICAL FINDINGS                │
│  (At least ONE positive finding, ≤30 days)   │
│                                              │
│  ☐ Positive McMurray's test                  │
│  ☐ Joint line tenderness + mechanical sx     │
│  ☐ Positive Lachman test                     │
│  ☐ Positive anterior/posterior drawer        │
│  ☐ Effusion >4 weeks                         │
│                                              │
│  Exam Date: _____________________________   │
│                                              │
├──────────────────────────────────────────────┤
│  SECTION 3: PRIOR IMAGING                    │
│  (ALL required)                              │
│                                              │
│  ☐ X-rays completed                          │
│  ☐ Weight-bearing views                      │
│  Date of X-rays: ________________________   │
│  (Must be within 60 days of PA request)      │
│                                              │
├──────────────────────────────────────────────┤
│  SECTION 4: CONSERVATIVE TREATMENT           │
│  (Check at least 2 of 5)                     │
│                                              │
│  ☐ Physical therapy ≥6 weeks                 │
│    Start: _________ Weeks: ____ Freq: ____  │
│  ☐ NSAIDs/analgesics ≥4 weeks               │
│    Med: _____________ Weeks: _____________  │
│  ☐ Activity modification                     │
│  ☐ Bracing/orthotics                         │
│  ☐ Intra-articular injection                 │
│    Type: ____________ Date: ______________  │
│                                              │
│  ★ EXCEPTION: Skip Section 4 if any apply:  │
│  ☐ Acute trauma (can't bear weight + ≥1     │
│    more: locked knee, suspected rupture)     │
│  ☐ Red flag: infection/tumor/fracture        │
│  ☐ Post-op within 6 months                   │
│    Surgery date: ________ Type: __________  │
│                                              │
├──────────────────────────────────────────────┤
│  ⚠ COMMON DENIAL REASONS                     │
│  • Anterior knee pain alone (no mech sx)     │
│  • "Knee pain" without specific diagnosis    │
│  • Repeat MRI <12mo without clinical change  │
│  • PT documented without dates/duration      │
│  • Equivocal exam findings                   │
│                                              │
├──────────────────────────────────────────────┤
│  SUBMISSION NOTES                            │
│  Auth valid 60 days from approval.           │
│  Include: order, clinical notes, X-ray rpt.  │
│  Standard decision: 7 days. Urgent: 72 hrs.  │
│                                              │
│  Completed by: _____________ Date: ________  │
└──────────────────────────────────────────────┘
```

**Implementation:** Use `reportlab` to generate the PDF with fillable form fields (AcroForm). Checkboxes are actual form checkboxes. Text fields are actual text inputs. The clinician opens in Adobe Acrobat/Reader, fills it out, saves it locally. Their PHI never touches your server.

### 3. Web Frontend

**Simple React app. Three views:**

**View 1: Payer + Procedure Selector**
```
┌────────────────────────────────────────┐
│  What are you submitting a PA for?     │
│                                        │
│  Payer:     [EviCore (Aetna/Cigna) ▼]  │
│  Procedure: [MRI Knee w/o Contrast ▼]  │
│                                        │
│  [Show Requirements]                   │
└────────────────────────────────────────┘
```

**View 2: Interactive Checklist**
The rules.json rendered as an interactive, readable checklist in the browser. No data is saved — this is a reference view. Sections are expandable/collapsible. ICD-10 codes are searchable. Exception pathways are visually distinct. Denial tips are highlighted.

**View 3: Download**
"Download Fillable PDF Checklist" button. Generates PDF on the server from the rules.json. Clinician saves and fills locally.

### 4. Simplified Backend

```python
# The entire backend is essentially this:

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path
import json

app = FastAPI(title="PA Checklist")

RULES_DIR = Path("rules")

@app.get("/api/payers")
def list_payers():
    """Return available payer/CPT combinations."""
    index = json.loads((RULES_DIR / "metadata/payer_cpt_index.json").read_text())
    return index

@app.get("/api/checklist/{payer_id}/{cpt_code}")
def get_checklist(payer_id: str, cpt_code: str):
    """Return the checklist data for a payer/CPT combination."""
    rules_file = RULES_DIR / f"{payer_id}_{cpt_code}.rules.json"
    if not rules_file.exists():
        raise HTTPException(404, f"No checklist for {payer_id}/{cpt_code}")
    return json.loads(rules_file.read_text())

@app.get("/api/checklist/{payer_id}/{cpt_code}/pdf")
def download_checklist_pdf(payer_id: str, cpt_code: str):
    """Generate and return a fillable PDF checklist."""
    rules = json.loads((RULES_DIR / f"{payer_id}_{cpt_code}.rules.json").read_text())
    pdf_path = generate_fillable_pdf(rules)  # reportlab
    return FileResponse(pdf_path, media_type="application/pdf",
                       filename=f"pa_checklist_{payer_id}_{cpt_code}.pdf")

@app.get("/api/icd10/search")
def search_icd10(q: str):
    """Search ICD-10 codes by description or code prefix."""
    # Static lookup from bundled ICD-10 database
    results = search_icd10_db(q)
    return results[:20]
```

That's it. No database. No authentication (for MVP). No file uploads. No PHI. Deployable on a $5/month VPS or free-tier Vercel/Railway.

---

## Revised Repository Structure

```
pa-checklist/
├── frontend/
│   ├── src/
│   │   ├── App.jsx                    # Router: selector → checklist → download
│   │   ├── components/
│   │   │   ├── PayerSelector.jsx       # Payer + CPT dropdown
│   │   │   ├── ChecklistView.jsx       # Interactive requirements display
│   │   │   ├── ChecklistSection.jsx    # Single section (diagnosis, imaging, etc.)
│   │   │   ├── ExceptionPathway.jsx    # Exception display with "waives" link
│   │   │   ├── DenialTips.jsx          # Common denial reasons callout
│   │   │   ├── ICD10Search.jsx         # Searchable ICD-10 code lookup
│   │   │   └── DownloadButton.jsx      # PDF download trigger
│   │   └── index.jsx
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── main.py                         # FastAPI app (4 endpoints, <100 lines)
│   ├── pdf_generator.py                # rules.json → fillable PDF (reportlab)
│   ├── icd10_search.py                 # ICD-10 code lookup
│   └── requirements.txt                # fastapi, uvicorn, reportlab
│
├── rules/                              # THE PRODUCT — curated rule files
│   ├── evicore_73721.rules.json
│   ├── evicore_73722.rules.json
│   ├── utah_medicaid_73721.rules.json
│   ├── registries/
│   │   └── knee_mri.registry.json
│   ├── metadata/
│   │   └── payer_cpt_index.json        # Master index
│   └── drafts/                         # LLM-generated, pre-review
│       └── ...
│
├── tools/                              # Build-time tooling (NOT deployed)
│   ├── compile_policy.py               # LLM policy compiler (reused from v1)
│   ├── validate_rules.py               # Rule validation (reused from v1)
│   └── icd10_import.py                 # Import ICD-10 database
│
├── data/
│   └── icd10_codes.json                # ICD-10 code database (public domain)
│
├── deferred/                           # V2 components (saved, not deployed)
│   ├── evidence.py                     # Patient chart extraction
│   ├── rule_engine.py                  # Deterministic rule evaluation
│   ├── ingestion.py                    # Chart PDF → text
│   ├── orchestration.py                # Full PA pipeline
│   └── rag_pipeline/                   # FAISS, embeddings, retrieval
│
└── README.md
```

---

## Build-Time Workflow: Adding a New Payer/CPT

This is identical to your existing workflow, minus the FAISS step:

```bash
# 1. Get the policy document
#    EviCore: download PDF from evicore.com/provider/clinical-guidelines
#    Aetna:   browse aetna.com/cpb/medical/ for the relevant CPB
#    Save to: policy_sources/evicore_msk_imaging_v1.0.2025.pdf

# 2. Extract text from the policy PDF (reuse your existing pdfplumber code)
python -c "
import pdfplumber
with pdfplumber.open('policy_sources/evicore_msk_imaging_v1.0.2025.pdf') as pdf:
    text = '\n'.join(page.extract_text() for page in pdf.pages)
    open('policy_sources/evicore_msk_imaging_v1.0.2025.txt', 'w').write(text)
"

# 3. Run the policy compiler to generate a draft (reuse compile_policy.py)
#    The compiler prompt needs updating to output the new checklist_sections
#    format instead of the old canonical_rules format — see section below
python tools/compile_policy.py \
  --input policy_sources/evicore_msk_imaging_v1.0.2025.txt \
  --payer evicore \
  --cpt 73721 \
  --section "MS-25 Knee" \
  --output rules/drafts/evicore_73721_draft.json

# 4. Validate the draft against the field registry
python tools/validate_rules.py \
  --registry rules/registries/knee_mri.registry.json \
  --rules rules/drafts/evicore_73721_draft.json

# 5. Human review: open the draft, compare to the actual policy PDF,
#    fix any errors, add help_text and denial tips, verify ICD-10 codes
#    This is THE critical step. Budget 2-3 hours per payer/CPT.

# 6. Promote to production
cp rules/drafts/evicore_73721_draft.json rules/evicore_73721.rules.json

# 7. Update the master index
python tools/update_index.py  # or edit payer_cpt_index.json manually

# 8. Commit and deploy
git add rules/evicore_73721.rules.json
git commit -m "Add EviCore knee MRI 73721 checklist"
```

---

## Updated Compiler Prompt

The compiler prompt from `architecture_guide.md` needs one change: output the `checklist_sections` format instead of the raw `canonical_rules` format. The structural logic is the same (`any`, `all`, `count_gte`), but each item gets human-facing fields.

```python
COMPILER_SYSTEM_PROMPT = """
You are a medical policy compiler. Convert insurance PA policy documents
into structured checklist data that a clinic billing person can use.

OUTPUT FORMAT:
{
  "payer": "...",
  "cpt_code": "...",
  "policy_source": "document title and section reference",
  "policy_effective_date": "YYYY-MM-DD",

  "checklist_sections": [
    {
      "id": "snake_case_id",
      "title": "Human-Readable Section Title",
      "description": "What this section requires, in plain English",
      "requirement_type": "any | all | count_gte",
      "threshold": N,  // only for count_gte
      "help_text": "Guidance for the person filling out the checklist",
      "items": [
        {
          "field": "snake_case_field_name",
          "label": "What to check or fill in",
          "help_text": "Specific documentation guidance",
          "icd10_codes": ["M23.200", ...],  // if applicable
          "input_type": "checkbox | date | number | text | checkbox_with_detail",
          "detail_fields": [...]  // only for checkbox_with_detail
        }
      ]
    }
  ],

  "exception_pathways": [...],  // same structure, adds "waives" array
  "exclusions": [...],
  "denial_prevention_tips": ["...", "..."],
  "submission_reminders": ["...", "..."]
}

FIELD NAMING: Use the provided field registry for canonical names.
HELP TEXT: Write for a billing coordinator, not a physician. Be specific
  about what documentation the payer expects to see.
DENIAL TIPS: Include the most common denial reasons you can identify
  from the policy language.
ICD-10 CODES: Include specific codes when the policy references them.
"""
```

---

## Deployment

**MVP deployment — dead simple:**

```
Option A: Single VPS ($5-10/month)
  - Nginx serves React build (static files)
  - Uvicorn runs FastAPI backend
  - rules/ directory is just files on disk
  - PDF generation happens on-demand

Option B: Serverless / Free tier
  - Frontend: Vercel or Netlify (free)
  - Backend: Railway or Render free tier
  - rules/ files bundled with the backend deploy
  - No database, no file storage, no secrets management
```

No Docker required for MVP. No CI/CD pipeline required for MVP. `git push` and restart the server.

---

## ICD-10 Code Database

Small clinics google ICD-10 codes. Include a searchable lookup as a value-add.

The CMS ICD-10-CM code set is public domain. Download from CMS.gov, parse into a JSON lookup:

```json
{
  "M23.200": {
    "code": "M23.200",
    "description": "Derangement of unspecified meniscus due to old tear or injury, right knee",
    "category": "Meniscal derangement",
    "chapter": "13 - Musculoskeletal"
  }
}
```

This is a static file (~70K codes, ~15MB JSON). Bundle it with the app. Searchable by code prefix or description keyword. The billing person types "meniscal tear" and sees the matching codes with descriptions.

---

## Revenue Model for MVP

**Free tier:** Browse checklists in the browser for any available payer/CPT. See requirements, ICD-10 codes, denial tips. Limited to 2-3 payer/CPT combos.

**Paid tier ($29-79/month per clinic):**
- Download fillable PDF checklists
- Access all payer/CPT combinations
- ICD-10 code search
- Email alerts when policy criteria change (future)
- Priority requests for new payer/CPT additions

**Why would they pay?** Because right now they're spending 20-30 minutes per PA googling requirements, reading payer PDFs, and piecing together checklists manually. If you cover the 5-6 most common imaging procedures across their top 3-4 payers, that's 15-24 checklists that save them time on every single PA.

---

## Phase 2 Path (After Paying Customers)

Once you have clinics using the checklists and providing feedback:

1. **Interactive web checklist with local evaluation.** The rule engine runs in the browser (JavaScript). The clinician fills in the checklist in the web UI. The app evaluates locally (no data sent to server) and shows pass/fail per section with specific gap guidance. Still no PHI on your servers.

2. **Optional chart upload with LLM pre-fill.** Reintroduce `evidence.py` and `orchestration.py`. Clinician uploads a chart. LLM pre-fills the checklist fields. Clinician reviews and corrects. Now you need HIPAA — but you have revenue and customer data to justify the investment.

3. **CMS-0057-F FHIR integration.** By January 2027, payers must expose PA criteria via FHIR APIs. Build a translation layer from FHIR Coverage Requirements Discovery (CRD) responses to your checklist format. This automates the policy compilation step and keeps checklists up to date automatically.

---

## First Week: What to Build

| Day | Task |
|-----|------|
| 1 | Download EviCore MSK Imaging Guidelines PDF. Extract text. Read the Knee section (MS-25). |
| 2 | Run your existing `compile_policy.py` against the real EviCore knee MRI criteria. Review draft output. |
| 3 | Manually curate `evicore_73721.rules.json` in the new checklist format. Validate against registry. |
| 4 | Build `pdf_generator.py` — convert rules.json to fillable PDF using reportlab. |
| 5 | Build minimal FastAPI backend (3-4 endpoints). Serve checklist data + PDF download. |
| 6-7 | Build React frontend — payer selector, checklist view, download button. |

End of week 1: A working app where someone can select "EviCore / Knee MRI 73721" and download a fillable PDF checklist built from real policy criteria. That's your demo for customer conversations.
