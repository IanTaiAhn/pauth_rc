"""
Policy Compiler — index-build time step (no PHI).

Reads the full text of a payer policy document and uses an LLM (Groq) to
produce two artifacts:

  canonical_rules   — list of evaluable rule objects for rule_engine.py
  extraction_schema — dict mapping field names to descriptions (what to
                      extract from a patient chart to evaluate the rules)

The output is validated and saved to:
  rag_pipeline/compiled_rules/{payer}_{cpt_code}.json

This script never receives patient data and has no PHI. Any LLM provider is
acceptable here; Groq is used by default.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.rag_pipeline.generation.generator import MedicalGenerator

logger = logging.getLogger(__name__)

# Directory where compiled rule sets are stored
COMPILED_RULES_DIR = Path(__file__).resolve().parent.parent / "compiled_rules"

# Valid logic operators supported by rule_engine.py
VALID_LOGIC_OPERATORS = {"all", "any", "count_gte", "count_lte"}

# Operators that require a numeric threshold
COUNT_OPERATORS = {"count_gte", "count_lte"}


def _build_prompt(policy_text: str, payer: str, cpt_code: str) -> str:
    """
    Build the structured extraction prompt sent to the LLM.

    The prompt asks the model to read the full policy document and produce a
    JSON object with two keys:

    - canonical_rules: list of rule objects the rule engine can evaluate
    - extraction_schema: dict of field names to descriptions

    Rule object schema:
      {
        "id": str,                          # snake_case unique identifier
        "description": str,                 # human-readable description
        "logic": "all" | "any" | "count_gte" | "count_lte",
        "threshold": int,                   # required when logic is count_gte/count_lte
        "conditions": [
          { "field": str, "operator": str, "value": any }
        ],
        "exception_pathway": true,          # optional — waives rules listed in overrides
        "exclusion": true,                  # optional — immediate exclusion if condition fails
        "overrides": ["rule_id", ...]       # optional — list of rule IDs waived by exception
      }

    Valid operators for conditions: eq, neq, gte, gt, lte, lt, in, contains, any_in
    """
    return f"""You are a medical policy analyst. Your task is to read the following payer policy document and extract structured prior authorization (PA) rules for CPT code {cpt_code} under payer "{payer}".

Output ONLY a valid JSON object with exactly two top-level keys:

1. "canonical_rules" — a JSON array of rule objects.
2. "extraction_schema" — a JSON object mapping every field name referenced in conditions to a plain-English description of what to extract from a patient chart.

Rule object structure:
{{
  "id": "<snake_case_unique_id>",
  "description": "<human-readable description of what this rule checks>",
  "logic": "<all | any | count_gte | count_lte>",
  "threshold": <integer, REQUIRED when logic is count_gte or count_lte>,
  "conditions": [
    {{ "field": "<field_name>", "operator": "<eq|neq|gte|gt|lte|lt|in|contains|any_in>", "value": <value> }}
  ],
  "exception_pathway": true,           (include only if this is an exception rule)
  "exclusion": true,                   (include only if a failed condition means immediate exclusion)
  "overrides": ["<rule_id>", ...]      (include only for exception rules, lists rule IDs this waives)
}}

Logic operator meanings:
- "all"       : every condition must pass (AND)
- "any"       : at least one condition must pass (OR)
- "count_gte" : at least `threshold` conditions must pass
- "count_lte" : at most `threshold` conditions must pass

Boolean field values must be JSON true or false (not strings).

Extraction schema format:
{{
  "<field_name>": "<description of what this field represents and how to extract it from a chart>"
}}

Every field name used in any condition must appear as a key in extraction_schema.

IMPORTANT:
- Output only the JSON object. Do not add markdown code fences, commentary, or any text before or after the JSON.
- Use snake_case for all field names and rule IDs.
- Be exhaustive: capture every PA criterion, exclusion, and exception pathway documented in the policy.
- For conservative treatment requirements with "at least N of the following" language, use logic "count_gte" with the appropriate threshold.
- For exclusion criteria (cases where coverage is denied outright), set "exclusion": true.
- For exception pathways that waive standard criteria, set "exception_pathway": true and list the rule IDs they override in "overrides".

---
POLICY DOCUMENT:
{policy_text}
---

JSON OUTPUT:"""


def _extract_json_from_response(raw: str) -> Optional[dict]:
    """
    Extract the first complete JSON object from the LLM response.

    The model may include surrounding text, markdown fences, or partial
    preamble. This function strips those and returns the parsed dict, or
    None if parsing fails.
    """
    if not raw:
        return None

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()

    # Find the outermost JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1

    if start < 0 or end <= start:
        logger.warning("No JSON object found in LLM response")
        return None

    json_str = cleaned[start:end]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning(f"JSON parse failed: {exc}")
        return None


def _validate_output(data: dict) -> list[str]:
    """
    Validate the LLM output and return a list of validation error strings.

    Checks:
    1. canonical_rules is a list
    2. extraction_schema is a dict
    3. Each rule has required fields (id, description, logic, conditions)
    4. Each rule's logic operator is valid
    5. count_gte / count_lte rules have a numeric threshold
    6. Every field referenced in any condition exists in extraction_schema
    """
    errors: list[str] = []

    canonical_rules = data.get("canonical_rules")
    extraction_schema = data.get("extraction_schema")

    # Top-level structure checks
    if not isinstance(canonical_rules, list):
        errors.append("'canonical_rules' must be a list")
        canonical_rules = []

    if not isinstance(extraction_schema, dict):
        errors.append("'extraction_schema' must be a dict")
        extraction_schema = {}

    schema_fields = set(extraction_schema.keys())

    for i, rule in enumerate(canonical_rules):
        rule_id = rule.get("id", f"<rule[{i}]>")
        prefix = f"Rule '{rule_id}'"

        # Required fields
        for required_field in ("id", "description", "logic", "conditions"):
            if required_field not in rule:
                errors.append(f"{prefix}: missing required field '{required_field}'")

        # Logic operator validity
        logic = rule.get("logic")
        if logic is not None and logic not in VALID_LOGIC_OPERATORS:
            errors.append(
                f"{prefix}: invalid logic operator '{logic}'. "
                f"Must be one of: {sorted(VALID_LOGIC_OPERATORS)}"
            )

        # Threshold requirement for count operators
        if logic in COUNT_OPERATORS:
            threshold = rule.get("threshold")
            if threshold is None:
                errors.append(
                    f"{prefix}: logic '{logic}' requires a 'threshold' field"
                )
            elif not isinstance(threshold, (int, float)):
                errors.append(
                    f"{prefix}: 'threshold' must be a number, got {type(threshold).__name__}"
                )

        # Conditions structure and field coverage
        conditions = rule.get("conditions")
        if not isinstance(conditions, list):
            errors.append(f"{prefix}: 'conditions' must be a list")
            continue

        for j, condition in enumerate(conditions):
            cond_prefix = f"{prefix} condition[{j}]"

            if not isinstance(condition, dict):
                errors.append(f"{cond_prefix}: must be an object")
                continue

            for required_field in ("field", "operator", "value"):
                if required_field not in condition:
                    errors.append(f"{cond_prefix}: missing required field '{required_field}'")

            field_name = condition.get("field")
            if field_name and field_name not in schema_fields:
                errors.append(
                    f"{cond_prefix}: field '{field_name}' is not defined in extraction_schema"
                )

    return errors


def compile_policy(policy_text: str, payer: str, cpt_code: str) -> dict:
    """
    Compile a payer policy document into a structured rule set.

    This is an index-build-time operation. It does NOT receive patient data
    and has no PHI. Any LLM provider is acceptable; Groq is used by default.

    Args:
        policy_text: Full text of the payer policy document.
        payer:       Payer identifier (e.g. "utah_medicaid").
        cpt_code:    CPT code string (e.g. "73721").

    Returns:
        A dict with:
          - "canonical_rules": list of rule objects
          - "extraction_schema": dict of field name → description
          - "_validation_errors": list of validation error strings (empty if valid)
          - "_payer": payer identifier
          - "_cpt_code": CPT code
          - "_model": model used for compilation

    The dict is also saved to:
        rag_pipeline/compiled_rules/{payer}_{cpt_code}.json
    """
    logger.info(f"Compiling policy for payer={payer}, cpt_code={cpt_code}")

    # Initialise Groq generator (no PHI — any provider acceptable here)
    generator = MedicalGenerator(provider="groq")
    model_name = generator.model_name

    prompt = _build_prompt(policy_text, payer, cpt_code)

    # Use a high token limit — compiled rule sets can be large
    raw_response = generator.generate_answer(
        prompt,
        max_tokens=4096,
        temperature=0.0,
    )

    if not raw_response:
        logger.error("LLM returned an empty response")
        result = {
            "canonical_rules": [],
            "extraction_schema": {},
            "_validation_errors": ["LLM returned an empty response — no rules compiled"],
            "_payer": payer,
            "_cpt_code": cpt_code,
            "_model": model_name,
        }
        _save_result(result, payer, cpt_code)
        return result

    parsed = _extract_json_from_response(raw_response)

    if parsed is None:
        logger.error("Could not parse JSON from LLM response")
        result = {
            "canonical_rules": [],
            "extraction_schema": {},
            "_validation_errors": [
                "LLM response did not contain parseable JSON",
                f"Raw response (first 500 chars): {raw_response[:500]}",
            ],
            "_payer": payer,
            "_cpt_code": cpt_code,
            "_model": model_name,
        }
        _save_result(result, payer, cpt_code)
        return result

    # Validate structure and field coverage
    validation_errors = _validate_output(parsed)

    if validation_errors:
        logger.warning(
            f"Compiled rules for {payer}/{cpt_code} have {len(validation_errors)} validation error(s). "
            "Human review required before deploying."
        )
        for err in validation_errors:
            logger.warning(f"  - {err}")
    else:
        logger.info(
            f"Compiled {len(parsed.get('canonical_rules', []))} rules and "
            f"{len(parsed.get('extraction_schema', {}))} schema fields for "
            f"{payer}/{cpt_code} — no validation errors"
        )

    result = {
        "canonical_rules": parsed.get("canonical_rules", []),
        "extraction_schema": parsed.get("extraction_schema", {}),
        "_validation_errors": validation_errors,
        "_payer": payer,
        "_cpt_code": cpt_code,
        "_model": model_name,
    }

    _save_result(result, payer, cpt_code)
    return result


def _save_result(result: dict, payer: str, cpt_code: str) -> None:
    """
    Save the compiled rule set to disk.

    Creates the compiled_rules/ directory if it does not exist.
    """
    COMPILED_RULES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = COMPILED_RULES_DIR / f"{payer}_{cpt_code}.json"

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    logger.info(f"Compiled rules saved to {output_path}")
