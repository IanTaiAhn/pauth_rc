# P-Auth RC — Project Structure

## What This Does

Two LLM calls against the same insurance policy document:

1. **Structure** — LLM reads the policy and produces a checklist skeleton: sections, fields, requirement types, exception pathways, exclusions
2. **Detail** — LLM reads the policy again with the skeleton and fills in specifics: ICD-10 codes, timeframes, thresholds, exact documentation requirements, denial tips

Output: a complete policy checklist JSON that a clinic can use to verify PA readiness before submission.

No patient data. No PHI. No RAG. No Bedrock.

---

## Directory Structure

```
pauth_rc/
├── app/
│   ├── main.py                      # FastAPI app, mount router
│   │
│   ├── router.py                    # POST /api/compile — single endpoint
│   │
│   ├── services/
│   │   ├── compiler.py              # Orchestrates the two-step pipeline
│   │   ├── structurer.py            # Step 1: policy → checklist skeleton
│   │   └── detailer.py              # Step 2: skeleton + policy → filled checklist
│   │
│   ├── llm.py                       # Groq API wrapper
│   │
│   ├── schemas.py                   # Pydantic models for template JSON
│   │
│   ├── prompts/
│   │   ├── structure_prompt.py      # Prompt for Step 1
│   │   └── detail_prompt.py         # Prompt for Step 2
│   │
│   ├── validation.py                # Structural + semantic validation
│   │
│   └── reader.py                    # PDF/TXT → plain text
│
├── templates/                       # Output: compiled checklist JSONs
│   ├── utah_medicaid_73721.json
│   └── ...
│
├── policies/                        # Input: source policy documents
│   └── utah_medicaid_73721.txt
│
├── tests/
│   ├── test_compiler.py
│   └── test_validation.py
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## What Each File Does

### `main.py`
FastAPI app. Mounts the single router. Loads env vars. That's it.

### `router.py`
One endpoint: `POST /api/compile`. Accepts a policy file (PDF or TXT) + payer ID + CPT code. Calls `compiler.compile()`. Returns the checklist JSON and saves it to `templates/`.

### `services/compiler.py`
Orchestrates the two-step pipeline:

```python
def compile(policy_text: str, payer: str, cpt_code: str) -> PolicyTemplate:
    # Step 1: get the skeleton
    skeleton = structurer.create_skeleton(policy_text, payer, cpt_code)

    # Step 2: fill in the details
    filled = detailer.fill_details(policy_text, skeleton)

    # Validate
    errors = validate(filled)

    # Save and return
    save(filled, payer, cpt_code)
    return filled
```

### `services/structurer.py`
Step 1. Sends the policy text to Groq with a prompt that says: "Identify the sections, fields, requirement types, exceptions, and exclusions. Don't fill in specifics — just give me the structure."

Output is a skeleton like:
```json
{
  "checklist_sections": [
    {
      "id": "eligible_diagnosis",
      "title": "Eligible Diagnosis",
      "requirement_type": "any",
      "items": [
        { "field": "suspected_meniscal_tear", "label": "Suspected Meniscal Tear", "input_type": "checkbox" }
      ]
    },
    {
      "id": "conservative_treatment",
      "title": "Conservative Treatment Requirement",
      "requirement_type": "count_gte",
      "threshold": 2,
      "items": [
        { "field": "physical_therapy", "label": "Physical Therapy", "input_type": "checkbox" }
      ]
    }
  ],
  "exception_pathways": [...],
  "exclusions": [...]
}
```

The key win: the LLM focuses entirely on understanding the policy logic (any vs all vs count_gte, which exceptions waive which sections) without also trying to extract every ICD-10 code and documentation detail. This is where you got the `all` vs `count_gte` error — splitting the tasks reduces that risk.

### `services/detailer.py`
Step 2. Sends the policy text AND the skeleton back to Groq. The prompt says: "Here is the structure. Now fill in: ICD-10 codes, specific timeframes, documentation requirements, help_text, denial prevention tips, and submission reminders."

The LLM isn't deciding structure anymore — it's just extracting details into slots that already exist. This is a much easier task for an LLM and produces more consistent results.

### `llm.py`
Groq API wrapper. One file, one provider. Handles: API key, model selection, token limits, retry (2-3 attempts), JSON extraction from response.

```python
class GroqClient:
    def __init__(self):
        self.api_key = os.environ["GROQ_API_KEY"]
        self.model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    def generate(self, prompt: str, max_tokens: int = 4096) -> str:
        # call Groq, return raw text, retry on failure
        ...

    def generate_json(self, prompt: str, max_tokens: int = 4096) -> dict | None:
        # call generate(), strip markdown fences, parse JSON
        ...
```

### `schemas.py`
Pydantic models matching your existing JSON format:

```python
class TemplateItem(BaseModel):
    field: str
    label: str
    help_text: str | None = None
    input_type: str
    icd10_codes: list[str] | None = None
    detail_fields: list[dict] | None = None

class TemplateSection(BaseModel):
    id: str
    title: str
    description: str
    requirement_type: Literal["any", "all", "count_gte"]
    threshold: int | None = None
    help_text: str | None = None
    items: list[TemplateItem]

class ExceptionPathway(BaseModel):
    id: str
    title: str
    description: str
    waives: list[str]
    requirement_type: Literal["any", "all", "count_gte"]
    threshold: int | None = None
    help_text: str | None = None
    items: list[TemplateItem]

class Exclusion(BaseModel):
    id: str
    title: str
    description: str
    severity: str = "hard_stop"

class PolicyTemplate(BaseModel):
    payer: str
    cpt_code: str
    policy_source: str | None = None
    policy_effective_date: str | None = None
    checklist_sections: list[TemplateSection]
    exception_pathways: list[ExceptionPathway]
    exclusions: list[Exclusion]
    denial_prevention_tips: list[str]
    submission_reminders: list[str]
    validation_errors: list[str] = []
    model: str | None = None
```

### `validation.py`
Your current structural validation plus semantic checks:

```python
def validate(template: dict) -> list[str]:
    errors = []

    # Structural (existing)
    # - required fields present
    # - requirement_type is valid
    # - count_gte has threshold
    # - waives references valid section IDs

    # Semantic (new — catches the all vs count_gte problem)
    # - description says "at least X" → requirement_type should be count_gte
    # - description says "all of" → requirement_type should be all
    # - count_gte threshold doesn't exceed number of items
    # - exception waives list isn't empty

    return errors
```

### `prompts/structure_prompt.py` and `prompts/detail_prompt.py`
Prompt templates as functions. Separated from service logic so you can iterate on prompts without touching business logic.

### `reader.py`
PDF or TXT to plain text. Uses pdfplumber for PDFs. ~20 lines.

---

## API

One endpoint:

```
POST /api/compile
  Body: multipart/form-data
    - policy_file: PDF or TXT
    - payer: string (e.g., "utah_medicaid")
    - cpt_code: string (e.g., "73721")

  Returns: PolicyTemplate JSON

  Side effect: saves to templates/{payer}_{cpt_code}.json
```

---

## Why Two LLM Steps

Your current single-step approach asks the LLM to simultaneously:
- Understand the policy logic (any vs all vs count_gte)
- Identify all sections, exceptions, exclusions
- Extract every ICD-10 code, timeframe, and documentation detail
- Format everything into a specific JSON schema

Splitting into structure then detail means:
- Step 1 focuses on **logic** — getting requirement_type and section relationships right
- Step 2 focuses on **extraction** — filling in codes, dates, and documentation specifics into an existing structure
- Each prompt is shorter and more focused
- You can validate the skeleton before spending tokens on detail extraction
- If Step 2 produces bad details, you re-run Step 2 only (the structure is stable)

---

## Environment

```bash
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile    # optional, has default
TEMPLATES_DIR=./templates               # optional, has default
LOG_LEVEL=INFO                          # optional
```

## Dependencies

```
fastapi
uvicorn
pydantic
pdfplumber
groq
python-multipart
```

---

## Running

```bash
cd pauth_rc
uvicorn app.main:app --reload --port 8000
```

## File Count

11 Python files + prompts. That's it.
