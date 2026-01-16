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