# P-Auth RC: Long-Term Architecture Guide
## Policy-Driven Rule Generation & Patient Schema Derivation

**Document scope:** How to eliminate the lossy re-interpretation layer between RAG
extraction and rule evaluation, scale to new CPT codes without hand-coding, and
stay on the right side of HIPAA/BAA requirements throughout.

---

## 1. The Core Problem with the Current Architecture

The current pipeline has a two-step lossy translation that compounds errors:

```
Policy PDF
  → RAG retrieval (good)
  → LLM produces summary JSON  ← STEP 1: information loss
      { "prerequisites": ["6 weeks PT", "X-rays within 60 days"] }
  → normalize_policy_criteria() re-interprets that string ← STEP 2: more loss
      generates PT rule, misses "at least 2 of N modalities"
  → rule_engine.py evaluates (correct, but fed incomplete rules)
```

The same problem exists on the patient side:

```
Chart text
  → LLM extracts to hand-coded schema  ← schema was written for knee MRI 73721
  → normalize_patient_evidence() maps to canonical fields ← fields missing for
                                                             shoulder, spine, etc.
  → rule_engine.py evaluates against incomplete patient data
```

The fix is to make each policy document the **source of truth** for both:
1. The evaluable rule structure (what the rule engine receives)
2. The patient extraction schema (what fields the LLM looks for in the chart)

This means the LLM's job changes from "summarize this policy" to
"produce a machine-executable rule set from this policy."

---

## 2. Target Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  INDEX-BUILD TIME  (runs once per policy document upload)       │
│                                                                 │
│  Policy PDF/TXT                                                 │
│       │                                                         │
│       ├──► Chunker ──► FAISS index  (unchanged)                 │
│       │                                                         │
│       └──► Policy Compiler (NEW)                                │
│               │                                                 │
│               ├──► canonical_rules.json   (evaluable rules)     │
│               └──► extraction_schema.json (patient fields)      │
│                         │                                       │
│                    stored alongside FAISS index                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  REQUEST TIME  (runs per patient chart submission)              │
│                                                                 │
│  Patient chart                                                  │
│       │                                                         │
│       └──► Schema-Driven Extractor (NEW)                        │
│               reads extraction_schema.json for this CPT         │
│               prompts LLM with targeted field list              │
│               returns validated patient_data                    │
│                                                                 │
│  canonical_rules.json  ──►  rule_engine.py  ◄──  patient_data  │
│                                   │                             │
│                              OrchestrationResponse              │
└─────────────────────────────────────────────────────────────────┘
```

**What disappears:**
- `normalize_policy_criteria()` — rules come out of the compiler ready to evaluate
- `normalize_patient_evidence()` — patient schema is derived per CPT, not hand-coded
- The string-parsing logic in `normalized_custom.py` that misses "at least 2 of N"

**What stays:**
- `rule_engine.py` — it is correct, it just needs richer input
- FAISS + RAG — still used at request time for exception detection (see Section 6)
- `extract_policy_rules.py` — repurposed as the Policy Compiler

---

## 3. Phase 1 — The Policy Compiler

### 3.1 What It Does

The Policy Compiler runs **once per policy document** at index-build time.
It reads the full policy text (not chunked retrieval — the whole document)
and produces two JSON artifacts stored next to the FAISS index.

### 3.2 The Rule Schema

The current rule engine supports `logic: "all"` and `logic: "any"`.
To handle real policies you need two more operators:

```python
# rule_engine.py additions — add to evaluate_rule()

def evaluate_rule(patient_data: dict, rule: dict) -> dict:
    logic = rule.get("logic", "all")
    conditions = rule.get("conditions", [])
    threshold = rule.get("threshold", 1)  # used by count_gte / count_lte

    results = [evaluate_condition(patient_data, cond) for cond in conditions]

    if logic == "all":
        met = all(results)
    elif logic == "any":
        met = any(results)
    elif logic == "count_gte":
        # "at least N of the following"
        met = sum(results) >= threshold
    elif logic == "count_lte":
        # "no more than N"
        met = sum(results) <= threshold
    else:
        met = False
```

This single addition lets you express Utah Medicaid Section 2.4 correctly:

```json
{
  "id": "conservative_treatment",
  "description": "At least 2 of: PT≥6wks, NSAIDs≥4wks, activity modification, bracing, injection",
  "logic": "count_gte",
  "threshold": 2,
  "conditions": [
    { "field": "pt_duration_weeks",     "operator": "gte", "value": 6 },
    { "field": "nsaid_weeks",           "operator": "gte", "value": 4 },
    { "field": "activity_mod_documented","operator": "eq",  "value": true },
    { "field": "bracing_documented",    "operator": "eq",  "value": true },
    { "field": "injection_documented",  "operator": "eq",  "value": true }
  ]
}
```

### 3.3 The Compiler Prompt

The key insight is that you give the LLM the **full policy text** (not retrieved
chunks) and ask it to produce the rule JSON directly. This is the one place where
sending the full document to the LLM is justified — it only happens at index-build
time, not per patient request.

```python
# backend/app/rag_pipeline/scripts/compile_policy.py

COMPILER_SYSTEM_PROMPT = """
You are a medical policy compiler. Your job is to convert insurance prior
authorization policy documents into machine-executable rule sets.

You must produce two JSON objects:

1. canonical_rules — a list of evaluable rules the rule engine will run
2. extraction_schema — the fields that must be extracted from a patient chart
   to evaluate these rules

RULE LOGIC VALUES:
- "all"        — all conditions must be true (AND)
- "any"        — at least one condition must be true (OR)
- "count_gte"  — at least `threshold` conditions must be true
- "count_lte"  — at most `threshold` conditions must be true

CONDITION OPERATORS:
eq, neq, gte, gt, lte, lt, in, not_in, contains

FIELD NAMING CONVENTION:
Use snake_case. Prefix by category:
  pt_           physical therapy
  nsaid_        NSAID medication
  imaging_      prior imaging
  injection_    injection therapy
  bracing_      bracing/orthotics
  activity_     activity modification
  exam_         physical examination findings
  notes_        clinical notes metadata
  patient_      patient demographics
  red_flag_     red flag symptoms
  postop_       post-operative context

EXTRACTION SCHEMA FORMAT:
For each field referenced in your rules, provide:
- field: snake_case name (matches rule condition field)
- type: string | boolean | integer | float | date | enum
- enum_values: list (only for type=enum)
- description: what to look for in the chart
- required: true | false
- default: value if not found (null if no sensible default)

EXCEPTION RULES:
Model exceptions as rules with a special "exception_pathway" flag.
When an exception rule passes, it OVERRIDES the failed standard rules
it covers (listed in "overrides" array).

OUTPUT FORMAT (respond with valid JSON only, no markdown):
{
  "payer": "...",
  "cpt_code": "...",
  "policy_version": "...",
  "compiled_at": "ISO-8601 timestamp",
  "canonical_rules": [ ...rule objects... ],
  "extraction_schema": [ ...field objects... ]
}
"""

COMPILER_USER_PROMPT = """
Compile this prior authorization policy into machine-executable rules.

Be exhaustive — capture every criterion, prerequisite, exception, and exclusion.
Do not summarize. Convert each policy requirement into a precise rule.

POLICY TEXT:
{policy_text}

CPT CODE: {cpt_code}
PAYER: {payer}

Output valid JSON only.
"""
```

### 3.4 Example Compiled Output for Utah Medicaid 73721

This is what the compiler should produce from the actual policy text you have.
This is the target — compare it to what `normalize_policy_criteria()` produces today.

```json
{
  "payer": "Utah Medicaid",
  "cpt_code": "73721",
  "policy_version": "DMHF-IMG-MRI-001",
  "canonical_rules": [

    {
      "id": "eligible_diagnosis",
      "description": "Member must have a diagnosis from Category A or B",
      "logic": "any",
      "conditions": [
        { "field": "exam_meniscal_tear_suspected",   "operator": "eq", "value": true },
        { "field": "exam_ligament_injury_suspected", "operator": "eq", "value": true },
        { "field": "exam_ocd_suspected",             "operator": "eq", "value": true },
        { "field": "exam_mechanical_symptoms",       "operator": "eq", "value": true },
        { "field": "exam_oa_surgical_planning",      "operator": "eq", "value": true }
      ]
    },

    {
      "id": "clinical_findings",
      "description": "At least one clinical finding documented within 30 days",
      "logic": "any",
      "conditions": [
        { "field": "exam_mcmurray_positive",         "operator": "eq", "value": true },
        { "field": "exam_thessaly_positive",         "operator": "eq", "value": true },
        { "field": "exam_joint_line_tender_mechanical","operator":"eq", "value": true },
        { "field": "exam_effusion_gt_4wks",          "operator": "eq", "value": true },
        { "field": "exam_lachman_positive",          "operator": "eq", "value": true },
        { "field": "exam_drawer_positive",           "operator": "eq", "value": true },
        { "field": "exam_varus_valgus_instability",  "operator": "eq", "value": true },
        { "field": "exam_mechanical_block_rom",      "operator": "eq", "value": true }
      ]
    },

    {
      "id": "prior_imaging",
      "description": "Weight-bearing X-rays within 60 days",
      "logic": "all",
      "conditions": [
        { "field": "imaging_xray_documented",  "operator": "eq",  "value": true },
        { "field": "imaging_xray_days_ago",    "operator": "lte", "value": 60 },
        { "field": "imaging_xray_weightbearing","operator": "eq", "value": true }
      ]
    },

    {
      "id": "conservative_treatment",
      "description": "At least 2 treatment modalities completed over minimum 6 weeks",
      "logic": "count_gte",
      "threshold": 2,
      "conditions": [
        { "field": "pt_duration_weeks",          "operator": "gte", "value": 6 },
        { "field": "nsaid_duration_weeks",       "operator": "gte", "value": 4 },
        { "field": "activity_mod_documented",    "operator": "eq",  "value": true },
        { "field": "bracing_documented",         "operator": "eq",  "value": true },
        { "field": "injection_documented",       "operator": "eq",  "value": true }
      ]
    },

    {
      "id": "notes_recency",
      "description": "Clinical notes within 30 days of PA request",
      "logic": "all",
      "conditions": [
        { "field": "notes_days_ago", "operator": "lte", "value": 30 }
      ]
    },

    {
      "id": "exception_acute_trauma",
      "description": "Acute trauma exception — waives conservative treatment",
      "logic": "count_gte",
      "threshold": 2,
      "exception_pathway": true,
      "overrides": ["conservative_treatment"],
      "conditions": [
        { "field": "red_flag_unable_to_bear_weight", "operator": "eq", "value": true },
        { "field": "red_flag_suspected_complete_rupture","operator":"eq","value": true },
        { "field": "red_flag_locked_knee",           "operator": "eq", "value": true }
      ]
    },

    {
      "id": "exception_postoperative",
      "description": "Post-op exception — waives conservative treatment if within 6mo of surgery",
      "logic": "all",
      "exception_pathway": true,
      "overrides": ["conservative_treatment"],
      "conditions": [
        { "field": "postop_within_6_months", "operator": "eq", "value": true }
      ]
    },

    {
      "id": "exception_red_flag",
      "description": "Red flag exception — infection/tumor/fracture, waives conservative treatment",
      "logic": "any",
      "exception_pathway": true,
      "overrides": ["conservative_treatment"],
      "conditions": [
        { "field": "red_flag_infection_suspected",  "operator": "eq", "value": true },
        { "field": "red_flag_tumor_suspected",      "operator": "eq", "value": true },
        { "field": "red_flag_occult_fracture",      "operator": "eq", "value": true }
      ]
    },

    {
      "id": "exclusion_workers_comp",
      "description": "Workers compensation cases are excluded — bill WC carrier",
      "logic": "all",
      "exclusion": true,
      "conditions": [
        { "field": "patient_workers_comp", "operator": "eq", "value": false }
      ]
    },

    {
      "id": "exclusion_no_symptoms",
      "description": "Routine screening without symptoms is excluded",
      "logic": "all",
      "exclusion": true,
      "conditions": [
        { "field": "exam_asymptomatic_screening", "operator": "eq", "value": false }
      ]
    }
  ],

  "extraction_schema": [
    { "field": "exam_mcmurray_positive",          "type": "boolean", "description": "McMurray's test documented as positive", "required": true, "default": false },
    { "field": "exam_thessaly_positive",          "type": "boolean", "description": "Thessaly test documented as positive", "required": false, "default": false },
    { "field": "exam_meniscal_tear_suspected",    "type": "boolean", "description": "Suspected meniscal tear as documented diagnosis", "required": true, "default": false },
    { "field": "exam_mechanical_symptoms",        "type": "boolean", "description": "Locking, catching, or giving-way documented", "required": true, "default": false },
    { "field": "exam_effusion_gt_4wks",           "type": "boolean", "description": "Joint effusion present for more than 4 weeks", "required": false, "default": false },
    { "field": "imaging_xray_documented",         "type": "boolean", "description": "X-ray of affected knee documented", "required": true, "default": false },
    { "field": "imaging_xray_days_ago",           "type": "integer", "description": "Days since X-ray was taken", "required": true, "default": null },
    { "field": "imaging_xray_weightbearing",      "type": "boolean", "description": "X-ray was weight-bearing view", "required": false, "default": true },
    { "field": "pt_duration_weeks",               "type": "integer", "description": "Weeks of physical therapy completed", "required": true, "default": null },
    { "field": "nsaid_duration_weeks",            "type": "integer", "description": "Weeks of NSAID or analgesic trial", "required": false, "default": null },
    { "field": "activity_mod_documented",         "type": "boolean", "description": "Activity modification documented", "required": false, "default": false },
    { "field": "bracing_documented",              "type": "boolean", "description": "Bracing or orthotics documented", "required": false, "default": false },
    { "field": "injection_documented",            "type": "boolean", "description": "Intra-articular injection documented", "required": false, "default": false },
    { "field": "notes_days_ago",                  "type": "integer", "description": "Days since clinical notes were written", "required": true, "default": 0 },
    { "field": "patient_workers_comp",            "type": "boolean", "description": "Is this a workers compensation claim", "required": true, "default": false },
    { "field": "red_flag_unable_to_bear_weight",  "type": "boolean", "description": "Patient unable to bear weight at evaluation", "required": false, "default": false },
    { "field": "red_flag_infection_suspected",    "type": "boolean", "description": "Signs of joint infection (fever, elevated markers, turbid aspirate)", "required": false, "default": false },
    { "field": "red_flag_tumor_suspected",        "type": "boolean", "description": "Suspected bone or soft tissue tumor", "required": false, "default": false },
    { "field": "postop_within_6_months",          "type": "boolean", "description": "Patient had knee surgery within the past 6 months", "required": false, "default": false }
  ]
}
```

Notice what this captures that the current system misses: `count_gte` for 2-of-N
conservative treatment, separate exam finding fields vs diagnosis fields,
weight-bearing flag on X-rays, exception rules with explicit `overrides` arrays,
and specific exclusion rules as first-class objects.

### 3.5 Compiler Implementation

```python
# backend/app/rag_pipeline/scripts/compile_policy.py

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

COMPILED_RULES_DIR = Path("backend/app/rag_pipeline/compiled_rules")


def compile_policy(
    policy_text: str,
    payer: str,
    cpt_code: str,
    llm_provider: str = "groq",
    model_name: str = "claude-sonnet-4-6",  # use Bedrock in prod for BAA
) -> dict:
    """
    Compile a policy document into machine-executable rules and extraction schema.

    This runs ONCE at index-build time, not per patient request.
    Output is stored as compiled_rules/{payer}_{cpt}.json

    Args:
        policy_text: Full text of the policy document
        payer: Payer identifier (e.g., "utah_medicaid")
        cpt_code: CPT code (e.g., "73721")
        llm_provider: LLM provider to use
        model_name: Model name

    Returns:
        Compiled rules dict with canonical_rules and extraction_schema
    """
    from app.rag_pipeline.generation.generator import generate_with_context

    prompt = COMPILER_USER_PROMPT.format(
        policy_text=policy_text,
        cpt_code=cpt_code,
        payer=payer
    )

    raw_output = generate_with_context(
        prompt=prompt,
        provider=llm_provider,
        model_name=model_name,
        max_tokens=4096,
        temperature=0.0,   # deterministic — this is a compiler, not a generator
        system_prompt=COMPILER_SYSTEM_PROMPT
    )

    # Parse and validate
    try:
        compiled = _parse_compiler_output(raw_output)
    except Exception as e:
        logger.error(f"Compiler output parse failed: {e}")
        raise

    # Validate rule structure
    errors = _validate_compiled_rules(compiled)
    if errors:
        logger.warning(f"Compiled rules have {len(errors)} validation issues: {errors}")
        # Do not fail — log and continue. Human review catches these.

    # Add metadata
    compiled["compiled_at"] = datetime.now(timezone.utc).isoformat()
    compiled["compiler_model"] = model_name
    compiled["validation_errors"] = errors

    # Persist
    _save_compiled_rules(compiled, payer, cpt_code)

    return compiled


def _parse_compiler_output(raw_output: str) -> dict:
    """Extract and parse JSON from compiler output."""
    # Strip markdown fences if model added them
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])

    json_start = cleaned.find("{")
    json_end = cleaned.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        raise ValueError("No JSON object found in compiler output")

    return json.loads(cleaned[json_start:json_end])


def _validate_compiled_rules(compiled: dict) -> list[str]:
    """
    Structural validation of compiled output.
    Returns list of error strings (empty = valid).
    """
    errors = []
    rules = compiled.get("canonical_rules", [])
    schema = compiled.get("extraction_schema", [])

    if not rules:
        errors.append("No canonical_rules generated")
    if not schema:
        errors.append("No extraction_schema generated")

    # Build set of declared schema fields
    schema_fields = {f["field"] for f in schema}

    for rule in rules:
        rule_id = rule.get("id", "unknown")

        # Check logic operator validity
        valid_logics = {"all", "any", "count_gte", "count_lte"}
        if rule.get("logic") not in valid_logics:
            errors.append(f"Rule '{rule_id}': invalid logic '{rule.get('logic')}'")

        # count_gte/count_lte require threshold
        if rule.get("logic") in {"count_gte", "count_lte"}:
            if "threshold" not in rule:
                errors.append(f"Rule '{rule_id}': count logic requires 'threshold'")

        # Every condition field must exist in extraction_schema
        for cond in rule.get("conditions", []):
            field = cond.get("field")
            if field and field not in schema_fields:
                errors.append(
                    f"Rule '{rule_id}': condition field '{field}' "
                    f"not in extraction_schema"
                )

        # Exception rules must declare what they override
        if rule.get("exception_pathway") and not rule.get("overrides"):
            errors.append(
                f"Rule '{rule_id}': exception_pathway=true but no 'overrides' list"
            )

    return errors


def _save_compiled_rules(compiled: dict, payer: str, cpt_code: str):
    """Persist compiled rules to disk."""
    COMPILED_RULES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = COMPILED_RULES_DIR / f"{payer}_{cpt_code}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(compiled, f, indent=2, ensure_ascii=False)

    logger.info(f"Compiled rules saved: {output_path}")


def load_compiled_rules(payer: str, cpt_code: str) -> Optional[dict]:
    """Load compiled rules for a payer/CPT combination."""
    path = COMPILED_RULES_DIR / f"{payer}_{cpt_code}.json"
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
```

---

## 4. Phase 2 — Schema-Driven Patient Extraction

### 4.1 The Core Change

Instead of the LLM being told "extract these fixed fields," it reads the
`extraction_schema` for the specific CPT code being requested and extracts
exactly the fields that the compiled rules need.

```python
# backend/app/services/evidence.py  (updated extract_evidence)

def build_extraction_prompt(chart_text: str, extraction_schema: list[dict]) -> str:
    """
    Build a chart extraction prompt from the compiled extraction schema.
    The schema comes from compile_policy() — it matches the rule engine fields exactly.
    """
    field_instructions = []
    output_template = {}

    for field_def in extraction_schema:
        field = field_def["field"]
        ftype = field_def["type"]
        desc = field_def["description"]
        default = field_def.get("default")
        enum_values = field_def.get("enum_values")

        # Build instruction line
        if enum_values:
            instruction = f'- "{field}": {desc}. Must be one of: {enum_values}. Default: {default}'
        elif ftype == "boolean":
            instruction = f'- "{field}": {desc}. true or false only. Default: {json.dumps(default)}'
        elif ftype in ("integer", "float"):
            instruction = f'- "{field}": {desc}. Number or null. Default: {json.dumps(default)}'
        elif ftype == "date":
            instruction = f'- "{field}": {desc}. YYYY-MM-DD format or null.'
        else:
            instruction = f'- "{field}": {desc}. Default: {json.dumps(default)}'

        field_instructions.append(instruction)
        output_template[field] = default

    fields_text = "\n".join(field_instructions)
    template_text = json.dumps(output_template, indent=2)

    return f"""You are a medical chart data extractor. Extract ONLY information
explicitly written in the chart note below. Do NOT infer or assume.

CRITICAL RULES:
1. Extract facts stated directly in the chart — do NOT interpret
2. If information is absent, use the default value shown in the template
3. For boolean fields: true only if explicitly documented, false if absent or denied
4. Output ONLY valid JSON — no other text

FIELDS TO EXTRACT:
{fields_text}

OUTPUT TEMPLATE (fill in values):
{template_text}

CHART NOTE:
\"\"\"
{chart_text}
\"\"\"

OUTPUT (valid JSON only):"""


def extract_evidence_schema_driven(
    chart_text: str,
    extraction_schema: list[dict],
    use_groq: bool = True,
) -> dict:
    """
    Extract patient evidence using a schema derived from the compiled policy rules.

    Args:
        chart_text: Full text of the patient chart
        extraction_schema: List of field definitions from compiled policy
        use_groq: Use Groq API (False = local model)

    Returns:
        Dict with extracted field values matching the schema
    """
    extractor = get_extractor(use_groq=use_groq)
    prompt = build_extraction_prompt(chart_text, extraction_schema)

    if use_groq:
        raw_output = extractor._generate_with_groq(prompt)
    else:
        raw_output = extractor._generate_with_local_model(prompt)

    extracted = json.loads(extractor._extract_json_object(raw_output))

    # Apply defaults for missing fields
    for field_def in extraction_schema:
        field = field_def["field"]
        if field not in extracted or extracted[field] is None:
            extracted[field] = field_def.get("default")

    # Run hallucination validation on any evidence_notes if present
    extracted = _validate_boolean_extraction(extracted, chart_text, extraction_schema)

    return extracted


def _validate_boolean_extraction(
    extracted: dict,
    chart_text: str,
    schema: list[dict]
) -> dict:
    """
    Spot-check boolean fields flagged as required.
    If a required boolean is True but no supporting text is found,
    flag it rather than silently accepting it.
    """
    chart_lower = chart_text.lower()
    validation_warnings = []

    for field_def in schema:
        field = field_def["field"]
        if field_def.get("type") != "boolean":
            continue
        if not field_def.get("required"):
            continue
        if not extracted.get(field):
            continue  # false positives (False values) don't need verification

        # Quick keyword check for the field description
        desc_keywords = [
            w for w in field_def["description"].lower().split()
            if len(w) > 4
        ]
        found_support = any(kw in chart_lower for kw in desc_keywords)
        if not found_support:
            validation_warnings.append(
                f"Field '{field}' is True but no supporting text found in chart"
            )

    extracted["_validation_warnings"] = validation_warnings
    extracted["_validation_passed"] = len(validation_warnings) == 0

    return extracted
```

### 4.2 Updated Orchestration Router

```python
# backend/app/routers/orchestration.py  (updated check_prior_auth)

@router.post("/check_prior_auth", response_model=OrchestrationResponse)
async def check_prior_auth(
    file: UploadFile = File(...),
    payer: str = Form(...),
    cpt: str = Form(...),
    include_diagnostics: bool = Query(default=False),
):
    # Step 1: Ingest file (unchanged)
    file_contents = await file.read()
    text = extract_text(file_contents)

    # Step 2: Load compiled rules for this payer/CPT
    compiled = load_compiled_rules(payer, cpt)
    if compiled is None:
        raise HTTPException(
            status_code=400,
            detail=f"No compiled rules found for {payer}/{cpt}. "
                   f"Run compile_policy() first."
        )

    extraction_schema = compiled["extraction_schema"]
    canonical_rules = compiled["canonical_rules"]

    # Step 3: Schema-driven patient extraction
    # The LLM extracts exactly the fields the rules need — nothing more
    patient_data = extract_evidence_schema_driven(
        chart_text=text,
        extraction_schema=extraction_schema,
        use_groq=True,
    )

    # Step 4: Evaluate rules directly — no normalization step
    evaluation = evaluate_all(
        patient_data=patient_data,
        policy_rules=canonical_rules,
        requested_cpt=cpt,
    )

    # Step 5: Build response (unchanged logic)
    ...
```

---

## 5. Updated Rule Engine for Exceptions and Exclusions

The compiler produces exception and exclusion rules as first-class objects.
The rule engine needs to handle them:

```python
# backend/app/rules/rule_engine.py  (additions)

def evaluate_all(
    patient_data: dict,
    policy_rules: list,
    requested_cpt: str = ""
) -> dict:
    """
    Evaluate all policy rules. Handles standard rules, exceptions, and exclusions.

    Evaluation order:
    1. Exclusion rules — if any pass (condition met), return EXCLUDED immediately
    2. Exception rules — if any pass, record which standard rules they override
    3. Standard rules — evaluate, but skip rules overridden by a passed exception
    4. Repeat imaging check (unchanged)
    """
    # Separate rule types
    exclusion_rules = [r for r in policy_rules if r.get("exclusion")]
    exception_rules = [r for r in policy_rules if r.get("exception_pathway")]
    standard_rules  = [r for r in policy_rules
                       if not r.get("exclusion") and not r.get("exception_pathway")]

    # 1. Check exclusions first
    for rule in exclusion_rules:
        result = evaluate_rule(patient_data, rule)
        if not result["met"]:
            # Exclusion condition NOT met = patient IS excluded
            return {
                "results": [result],
                "all_criteria_met": False,
                "total_rules": 1,
                "rules_met": 0,
                "rules_failed": 1,
                "excluded": True,
                "exclusion_reason": rule["description"],
                "warnings": [],
            }

    # 2. Evaluate exception rules — collect overrides
    overridden_rule_ids = set()
    exception_results = []
    exceptions_applied = []

    for rule in exception_rules:
        result = evaluate_rule(patient_data, rule)
        exception_results.append(result)
        if result["met"]:
            overridden_rule_ids.update(rule.get("overrides", []))
            exceptions_applied.append(rule["description"])

    # 3. Evaluate standard rules, skipping overridden ones
    standard_results = []
    for rule in standard_rules:
        result = evaluate_rule(patient_data, rule)
        if rule["id"] in overridden_rule_ids and not result["met"]:
            # Mark as overridden rather than failed
            result["overridden_by_exception"] = True
            result["met"] = True  # treat as passing for score purposes
        standard_results.append(result)

    # 4. Repeat imaging check (unchanged)
    warnings = []
    if requested_cpt:
        warning = RepeatImagingRule().evaluate(patient_data, requested_cpt)
        if warning:
            warnings.append(warning)

    all_results = exception_results + standard_results

    # Score only on standard rules (exception rules are informational)
    scoreable = [r for r in standard_results if r["rule_id"] != "evidence_quality"]
    rules_met = sum(1 for r in scoreable if r["met"])
    total_rules = len(scoreable)

    return {
        "results": all_results,
        "all_criteria_met": all(r["met"] for r in standard_results),
        "total_rules": total_rules,
        "rules_met": rules_met,
        "rules_failed": total_rules - rules_met,
        "excluded": False,
        "exclusion_reason": None,
        "exceptions_applied": exceptions_applied,
        "warnings": warnings,
    }
```

---

## 6. RAG at Request Time — Exception Evidence Retrieval

The RAG pipeline still has a role at request time, but it shifts from
"extract rules" to "retrieve supporting text for edge cases."

Specifically, when an exception rule partially passes (some conditions met,
not all), you can use RAG to retrieve the relevant policy section and surface
it to the clinician reviewer in the response.

```python
# In orchestration.py, after evaluation:

def retrieve_exception_guidance(
    exception_rule: dict,
    payer: str,
    cpt: str,
    index_name: str
) -> str:
    """
    If an exception rule partially applies, retrieve the full policy text
    for that exception so the clinician can assess manually.
    Only runs when a rule partially passes — not on every request.
    """
    query = f"{exception_rule['description']} {payer} {cpt} exception criteria"
    context = retrieve_and_format(
        query=query,
        store=build_index.STORE,
        embedder=build_index.EMBEDDER,
        top_k=3
    )
    if context:
        return context[0].get("text", "")
    return ""
```

This keeps RAG in the pipeline for its strength (finding relevant text)
without relying on it to produce structured output.

---

## 7. Adding a New CPT Code (The Operational Flow)

With this architecture, adding CPT 73722 (with contrast) or shoulder MRI
(73221) takes three steps:

```bash
# Step 1: Upload the policy document (existing endpoint, unchanged)
POST /api/upload_document
  file: utah_medicaid_73722_mri_knee_with_contrast.txt

# Step 2: Build the FAISS index (existing, unchanged)
python -c "from app.rag_pipeline.scripts.build_index_updated import build_index; build_index()"

# Step 3: NEW — compile the policy into rules + schema
python -c "
from app.rag_pipeline.scripts.compile_policy import compile_policy
from pathlib import Path

policy_text = Path('uploaded_docs/utah_medicaid_73722_mri_knee_with_contrast.txt').read_text()
compiled = compile_policy(
    policy_text=policy_text,
    payer='utah_medicaid',
    cpt_code='73722',
)
print(f'Compiled {len(compiled[\"canonical_rules\"])} rules')
print(f'Schema has {len(compiled[\"extraction_schema\"])} fields')
"
```

Then add the new entry to `INDEX_MAP` in orchestration.py. That is the
**entire** process for a new CPT code. No changes to `normalized_custom.py`,
no new fields in `evidence.py`, no hand-coding.

---

## 8. HIPAA and BAA Compliance

### 8.1 Where PHI Flows in the New Architecture

| Step | PHI Involved | External Call | BAA Required |
|------|-------------|---------------|-------------|
| Index build / Policy Compiler | **No PHI** — policy documents only | Yes (LLM) | No — no PHI |
| Schema-driven extraction | **Yes** — chart text with PHI | Yes (LLM) | **Yes** |
| Rule evaluation | **Yes** — patient field values | No — local only | N/A |
| FAISS retrieval | **No** — query is CPT/payer string | No — local | N/A |
| Compiled rules storage | **No** — rules only, no PHI | No | N/A |

The key insight: **the Policy Compiler is the only LLM call with no PHI**.
This means you can run the compiler against any LLM, including public APIs,
without BAA concerns. The extraction step (chart → structured fields) is the
only PHI-touching LLM call.

### 8.2 Provider Selection by Step

```
Policy Compiler (index-build time, NO PHI)
  → Any LLM is acceptable here
  → GPT-4o, Claude (public API), Llama via Groq all fine
  → This is where you want the most capable model for accuracy
  → Run this in a dev/ops environment, not in the patient request path

Patient Extractor (request time, PHI PRESENT)
  → Must use a BAA-covered provider
  → AWS Bedrock (Claude via Bedrock, Llama via Bedrock)   ← recommended
  → Azure OpenAI                                           ← acceptable
  → GCP Vertex AI                                         ← acceptable
  → Local Qwen2.5 (no external call)                      ← always acceptable
  → Groq: NOT acceptable until you have a signed BAA
           Groq's standard terms do not constitute a BAA
```

### 8.3 Bedrock Integration (Recommended Path)

```python
# backend/app/rag_pipeline/generation/generator.py  (add Bedrock provider)

import boto3
import json

class MedicalGenerator:
    def __init__(self, provider="local", model_name=None, api_key=None):
        self.provider = provider
        ...
        if provider == "bedrock":
            self._init_bedrock_client()

    def _init_bedrock_client(self):
        """
        AWS Bedrock — HIPAA-eligible with signed BAA.

        Prerequisites:
        1. Sign BAA with AWS: https://aws.amazon.com/compliance/hipaa-compliance/
        2. Enable HIPAA-eligible services in your AWS account
        3. Use a HIPAA-eligible region (us-east-1, us-west-2, etc.)
        4. Configure IAM role with bedrock:InvokeModel permission
        5. Do NOT log model inputs/outputs to CloudWatch without PHI controls

        Recommended models on Bedrock for PHI extraction:
        - anthropic.claude-sonnet-4-6       (best accuracy for structured extraction)
        - meta.llama3-70b-instruct-v1:0    (good performance, lower cost)
        """
        self.bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        if not self.model_name:
            # Claude on Bedrock — BAA-eligible, best extraction accuracy
            self.model_name = "anthropic.claude-sonnet-4-6"

    def _generate_bedrock(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate using AWS Bedrock — HIPAA-eligible."""

        # Claude on Bedrock uses the Messages API format
        if "anthropic" in self.model_name:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })
            response = self.bedrock_client.invoke_model(
                body=body,
                modelId=self.model_name,
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        # Llama on Bedrock
        elif "llama" in self.model_name:
            body = json.dumps({
                "prompt": prompt,
                "max_gen_len": max_tokens,
                "temperature": temperature,
            })
            response = self.bedrock_client.invoke_model(
                body=body,
                modelId=self.model_name,
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response["body"].read())
            return response_body["generation"]
```

### 8.4 Audit Logging for PHI Access (CRITICAL-5)

The new architecture creates a natural audit boundary. Every PHI-touching
operation passes through `extract_evidence_schema_driven()`. Add audit logging there:

```python
# backend/app/services/evidence.py

import logging
import hashlib
from datetime import datetime, timezone

phi_audit_logger = logging.getLogger("phi_audit")

def extract_evidence_schema_driven(
    chart_text: str,
    extraction_schema: list[dict],
    use_groq: bool = True,
    request_id: str = None,   # pass from orchestration router
    user_id: str = None,      # pass from auth middleware (once added)
) -> dict:
    # PHI ACCESS AUDIT LOG — required for HIPAA compliance
    # Log WHO accessed WHAT, not the PHI content itself
    phi_audit_logger.info(json.dumps({
        "event": "phi_access",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "user_id": user_id or "unauthenticated",   # fix when auth is added
        "operation": "chart_extraction",
        "chart_hash": hashlib.sha256(chart_text.encode()).hexdigest(),
        "schema_fields": len(extraction_schema),
        # Do NOT log chart_text or patient_name here
    }))

    # ... rest of extraction
```

Route `phi_audit_logger` to a separate, append-only log file or
CloudWatch Logs with restricted access. This log is your audit trail.

### 8.5 Compiled Rules Storage — No PHI Risk

The compiled rules (`canonical_rules.json`, `extraction_schema.json`) contain
zero PHI — they are derived from the policy document, not patient charts.
These can be stored in version control, backed up freely, and shared with
team members without any HIPAA considerations.

This is a meaningful improvement over the current architecture where the
FAISS store contains embeddings derived from policy text (no PHI) but is
stored alongside patient diagnostic output files.

### 8.6 The Open HIPAA Issues — Prioritized for This Architecture

| ID | Impact on New Architecture | Action |
|----|---------------------------|--------|
| CRITICAL-1 (no encryption at rest) | Compiled rules: low risk, no PHI. Patient data in transit: HIGH. | Encrypt `uploaded_docs/` and extraction outputs. Use S3 with SSE-KMS for cloud deploy. |
| CRITICAL-3 (no auth) | Every PHI-touching endpoint is unauthenticated. | Add FastAPI middleware + JWT before any real charts are processed. The new audit log stub needs a real `user_id`. |
| CRITICAL-4 (Groq BAA) | Groq is used in extractor. With new arch: Groq is fine for compiler (no PHI). Extractor MUST move to Bedrock. | Use `provider="bedrock"` in `extract_evidence_schema_driven()`. Keep Groq for compiler only. |
| HIGH-1 (hardcoded paths) | `MODEL_PATH` in `evidence.py` is Windows-absolute. Breaks any cloud deploy. | Use `pathlib.Path(__file__).resolve().parent` consistently. Already done in some files, not in `evidence.py`. |
| HIGH-4 (path traversal in upload) | `uploaded_docs/` directory. | Sanitize filenames: `Path(file.filename).name` only, reject `..` and `/`. |
| MED-5 (pickle for FAISS metadata) | Pickle deserialization is a known vector for arbitrary code execution. | Replace with `json.dumps()` for metadata storage. FAISS index itself stays binary. |

---

## 9. Migration Plan (Incremental, Not Big-Bang)

### Step 1 — Add `count_gte` / `count_lte` to rule engine
No breaking changes. Existing rules still work. Takes ~30 minutes.

### Step 2 — Write and validate the Policy Compiler for 73721
Run it against the Utah Medicaid 73721 policy. Compare its output to the
hand-coded rules in `normalized_custom.py`. Fix any discrepancies in the
compiler prompt. This is the validation step — you have ground truth
from your existing test cases (the 10 diagnostic artifacts).

### Step 3 — Run both pipelines in parallel
For each patient chart submission, run both the old normalization path and
the new compiled-rules path. Compare results. When they agree on all
10 test cases, retire the old path.

### Step 4 — Migrate extraction to schema-driven
Replace `extract_evidence()` calls with `extract_evidence_schema_driven()`.
Run against your synthetic test charts. Validate that each field maps
correctly to the compiled schema.

### Step 5 — Add Bedrock provider
Wire up the Bedrock client. Use it only in `extract_evidence_schema_driven()`.
Keep Groq for the Policy Compiler (no PHI). At this point CRITICAL-4 is resolved.

### Step 6 — Add CRITICAL-3 (auth)
Now that the pipeline is clean and the audit log has the right shape,
add FastAPI middleware. The audit logger already has the `user_id` stub — fill it in.

### Step 7 — Compile 73722 and 73723
Run the compiler. Add entries to `INDEX_MAP`. No code changes needed.

---

## 10. File Structure After Migration

```
backend/
├── app/
│   ├── rag_pipeline/
│   │   ├── compiled_rules/             ← NEW: policy compiler output
│   │   │   ├── utah_medicaid_73721.json
│   │   │   ├── utah_medicaid_73722.json
│   │   │   └── utah_medicaid_73723.json
│   │   └── scripts/
│   │       ├── build_index_updated.py  ← unchanged
│   │       ├── compile_policy.py       ← NEW: Policy Compiler
│   │       └── extract_policy_rules.py ← kept for RAG/exception retrieval
│   ├── services/
│   │   ├── evidence.py                 ← add extract_evidence_schema_driven()
│   │   └── ingestion.py                ← unchanged
│   ├── normalization/
│   │   └── normalized_custom.py        ← deprecated after Step 3; delete after Step 4
│   ├── rules/
│   │   └── rule_engine.py              ← add count_gte, exception/exclusion logic
│   └── routers/
│       └── orchestration.py            ← updated to load compiled rules
```

The key deletion is `normalized_custom.py` — 700 lines of fragile string parsing
replaced by a compiler prompt and a JSON file per CPT code.

---

## Summary

| Current | After Migration |
|---------|----------------|
| Policy rules derived by parsing LLM summary text | Rules produced directly by Policy Compiler from full policy text |
| Patient schema hand-coded in `evidence.py` | Patient schema derived from compiled rules per CPT code |
| "at least 2 of N" expressed as separate single-field rules | `count_gte` logic operator expresses it correctly |
| Exceptions detected in orchestration.py heuristically | Exception rules are first-class in the rule set with explicit `overrides` |
| Adding a CPT requires editing 3+ files | Adding a CPT = upload + build index + run compiler |
| Groq used for PHI extraction (no BAA) | Groq for compiler (no PHI), Bedrock for extraction (BAA-covered) |
| No audit log | PHI access logged at extraction boundary |
