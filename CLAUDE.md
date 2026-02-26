# P-Auth RC — Claude Code Context

## What This Is

A policy compiler that converts Medicare prior authorization (PA) policy documents into structured checklist JSONs. A clinic uses the checklist to verify they have the required documentation before submitting a PA request for total joint arthroplasty.

**Input:** A Medicare LCD policy document (PDF or TXT) for a specific LCD code.
**Output:** A structured JSON checklist with sections, fields, requirement logic, exceptions, exclusions, denial tips, and submission reminders.

This is the template-creation tool only. No patient data, no PHI, no chart extraction.

---

## Two-Step LLM Pipeline

Both steps use the same policy document. Both go through Groq. No PHI involved.

**Step 1 — Structure** (`services/structurer.py`)
LLM identifies the policy's logical skeleton: sections, fields, requirement types (`any`/`all`/`count_gte`), exception pathways and what they waive, exclusions. No detail extraction — just logic and structure.

**Step 2 — Detail** (`services/detailer.py`)
LLM receives the skeleton + the policy text again. Fills in: ICD-10 codes, timeframes, thresholds, documentation requirements, help_text, denial prevention tips, submission reminders. Structure is locked — the LLM only extracts into existing slots.

**Why split:** A single-step approach conflates logic interpretation with detail extraction. The `all` vs `count_gte` error on conservative treatment came from this. Splitting lets Step 1 focus on getting the logic right and Step 2 focus on filling in specifics.

---

## Project Structure

```
pauth_rc/
├── app/
│   ├── main.py                      # FastAPI app, mounts router
│   ├── router.py                    # POST /api/compile
│   ├── services/
│   │   ├── compiler.py              # Orchestrates: structurer → detailer → validate → save
│   │   ├── structurer.py            # Step 1: policy → skeleton JSON
│   │   └── detailer.py              # Step 2: skeleton + policy → filled checklist
│   ├── llm.py                       # Groq API wrapper (only LLM client)
│   ├── schemas.py                   # Pydantic models for the checklist JSON
│   ├── validation.py                # Structural + semantic validation
│   ├── reader.py                    # PDF/TXT → plain text (pdfplumber)
│   └── prompts/
│       ├── structure_prompt.py      # Prompt builder for Step 1
│       └── detail_prompt.py         # Prompt builder for Step 2
├── templates/                       # Output: compiled checklist JSONs
├── policies/                        # Input: source policy documents
├── tests/
├── .env.example
└── requirements.txt
```

---

## API

Single endpoint:

```
POST /api/compile
  multipart/form-data:
    policy_file: PDF or TXT
    payer: string         (e.g., "medicare")
    lcd_code: string      (e.g., "L36007")
  Returns: PolicyTemplate JSON
  Side effect: saves to templates/{payer}_{lcd_code}.json
```

---

## Compiled JSON Format

Requirement types on sections and exceptions:

| `requirement_type` | Meaning |
|---|---|
| `"any"` | At least one item must be met |
| `"all"` | Every item must be met |
| `"count_gte"` | At least `threshold` items must be met |

Exception pathways have a `waives` array listing which section IDs they override.
Exclusions are hard stops — if triggered, PA is not coverable.

---

## Code Rules

- **Prompts live in `prompts/`** — never inline prompt strings in service files.
- **`llm.py` is the only file that calls Groq** — services call `llm.py`, not the API directly.
- **`validation.py` checks both structure and semantics** — if a description says "at least X of," verify `requirement_type` is `count_gte` with a matching threshold.
- **All paths use `pathlib.Path` or env vars** — no hardcoded absolute paths.
- **Don't return tracebacks to HTTP clients** — log server-side, return clean error messages.
- **`schemas.py` is the source of truth** for the JSON shape. If the schema changes, update the Pydantic models first.

---

## Environment

```bash
GROQ_API_KEY=              # required
GROQ_MODEL=                # optional, defaults to llama-3.3-70b-versatile
TEMPLATES_DIR=./templates  # optional, defaults to ./templates
LOG_LEVEL=INFO             # optional
```

---

## Running

```bash
cd pauth_rc
uvicorn app.main:app --reload --port 8000
```

## Dependencies

```
fastapi, uvicorn, pydantic, pdfplumber, groq, python-multipart
```

---

## Current Scope

**In scope:** Medicare total joint arthroplasty (LCD L36007). Expanding by adding more LCD policy documents and running the compiler — no Python changes needed.

**Not in scope (yet):** Patient chart extraction, PHI handling, rule evaluation engine, frontend, EHR integration.
