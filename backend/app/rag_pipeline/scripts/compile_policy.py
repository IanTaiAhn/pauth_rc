"""
Policy Compiler — index-build time step (no PHI).

Reads the full text of a payer policy document and uses an LLM (Groq) to
produce a human-readable checklist for clinic billing staff:

  checklist_sections      — list of requirement sections (diagnosis, imaging, etc.)
  exception_pathways      — rules that waive certain requirements
  exclusions              — hard stop scenarios
  denial_prevention_tips  — common denial reasons
  submission_reminders    — important notes for PA submission

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

    The prompt asks the model to convert the policy into a human-readable
    checklist format for clinic billing staff.
    """
    return f"""You are a medical policy analyst converting insurance PA policies into checklists for clinic billing staff.

Read the following payer policy document and create a structured checklist for CPT code {cpt_code} under payer "{payer}".

Your audience is a billing coordinator (not a physician). Use plain English, be specific about what documentation is required, and highlight common denial reasons.

Output ONLY valid JSON with this exact structure:

{{
  "payer": "{payer}",
  "cpt_code": "{cpt_code}",
  "policy_source": "<document title and section reference>",
  "policy_effective_date": "YYYY-MM-DD or null if not stated",

  "checklist_sections": [
    {{
      "id": "snake_case_section_id",
      "title": "Human-Readable Section Title",
      "description": "What this section requires, in plain English",
      "requirement_type": "any | all | count_gte",
      "threshold": 2,  // ONLY include if requirement_type is count_gte
      "help_text": "Guidance for the person filling this out",
      "items": [
        {{
          "field": "snake_case_field_name",
          "label": "Short checkbox/field label (1-8 words)",
          "help_text": "Specific documentation guidance - what the payer expects to see",
          "icd10_codes": ["M23.200", "M23.201"],  // include if applicable, otherwise omit
          "input_type": "checkbox | date | number | text | checkbox_with_detail",
          "detail_fields": [...]  // ONLY for checkbox_with_detail - nested fields for additional info
        }}
      ]
    }}
  ],

  "exception_pathways": [
    {{
      "id": "exception_snake_case_id",
      "title": "Exception Title",
      "description": "What this exception does",
      "waives": ["section_id_1", "section_id_2"],  // which section IDs this exception waives
      "requirement_type": "any | all | count_gte",
      "threshold": 2,  // if count_gte
      "help_text": "When this exception applies",
      "items": [
        {{
          "field": "field_name",
          "label": "Label",
          "help_text": "Documentation requirements",
          "input_type": "checkbox"
        }}
      ]
    }}
  ],

  "exclusions": [
    {{
      "id": "exclusion_id",
      "title": "Exclusion Title",
      "description": "What scenarios are NOT covered",
      "severity": "hard_stop"
    }}
  ],

  "denial_prevention_tips": [
    "Common denial reason 1 — be specific about what triggers denials",
    "Common denial reason 2 with concrete documentation advice"
  ],

  "submission_reminders": [
    "Authorization valid X days from approval",
    "Include: list of required documents",
    "Decision timeline information"
  ]
}}

REQUIREMENTS:
- Use snake_case for all IDs and field names
- Labels and titles should be concise and clear
- help_text must be specific and actionable (not vague)
- Include ICD-10 codes when the policy references specific diagnoses
- requirement_type meanings:
  * "any" = at least ONE item must be checked
  * "all" = ALL items must be checked
  * "count_gte" = at least `threshold` items must be checked
- For input_type:
  * "checkbox" = simple yes/no checkbox
  * "date" = date field (often with validation like "within 30 days")
  * "number" = numeric field
  * "text" = free text field
  * "checkbox_with_detail" = checkbox that reveals additional fields when checked
- Be exhaustive: capture ALL requirements, exceptions, and exclusions
- Extract common denial reasons from policy language (look for "will be denied if..." patterns)
- Output ONLY the JSON - no markdown fences, no commentary

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
    Validate the LLM output checklist format.

    Checks:
    1. Required top-level fields exist
    2. checklist_sections is a list with valid structure
    3. Each section has required fields and valid requirement_type
    4. count_gte sections have a threshold
    5. exception_pathways and exclusions are valid
    """
    errors: list[str] = []

    # Check required top-level fields
    required_top_level = ["payer", "cpt_code", "checklist_sections"]
    for field in required_top_level:
        if field not in data:
            errors.append(f"Missing required top-level field: '{field}'")

    # Validate checklist_sections
    sections = data.get("checklist_sections")
    if not isinstance(sections, list):
        errors.append("'checklist_sections' must be a list")
        sections = []

    section_ids = set()
    valid_requirement_types = {"any", "all", "count_gte"}

    for i, section in enumerate(sections):
        section_id = section.get("id", f"<section[{i}]>")
        prefix = f"Section '{section_id}'"

        section_ids.add(section_id)

        # Required fields for sections
        for field in ("id", "title", "description", "requirement_type", "items"):
            if field not in section:
                errors.append(f"{prefix}: missing required field '{field}'")

        # Validate requirement_type
        req_type = section.get("requirement_type")
        if req_type and req_type not in valid_requirement_types:
            errors.append(
                f"{prefix}: invalid requirement_type '{req_type}'. "
                f"Must be one of: {sorted(valid_requirement_types)}"
            )

        # Check threshold for count_gte
        if req_type == "count_gte":
            threshold = section.get("threshold")
            if threshold is None:
                errors.append(f"{prefix}: requirement_type 'count_gte' requires a 'threshold' field")
            elif not isinstance(threshold, (int, float)):
                errors.append(f"{prefix}: 'threshold' must be a number")

        # Validate items
        items = section.get("items")
        if not isinstance(items, list):
            errors.append(f"{prefix}: 'items' must be a list")
            continue

        for j, item in enumerate(items):
            item_prefix = f"{prefix} item[{j}]"

            if not isinstance(item, dict):
                errors.append(f"{item_prefix}: must be an object")
                continue

            # Required fields for items
            for field in ("field", "label", "input_type"):
                if field not in item:
                    errors.append(f"{item_prefix}: missing required field '{field}'")

            # Validate input_type
            valid_input_types = {"checkbox", "date", "number", "text", "checkbox_with_detail"}
            input_type = item.get("input_type")
            if input_type and input_type not in valid_input_types:
                errors.append(
                    f"{item_prefix}: invalid input_type '{input_type}'. "
                    f"Must be one of: {sorted(valid_input_types)}"
                )

    # Validate exception_pathways
    exceptions = data.get("exception_pathways", [])
    if not isinstance(exceptions, list):
        errors.append("'exception_pathways' must be a list")
        exceptions = []

    for i, exception in enumerate(exceptions):
        exc_id = exception.get("id", f"<exception[{i}]>")
        prefix = f"Exception '{exc_id}'"

        # Required fields
        for field in ("id", "title", "waives", "requirement_type", "items"):
            if field not in exception:
                errors.append(f"{prefix}: missing required field '{field}'")

        # Validate waives references
        waives = exception.get("waives", [])
        if not isinstance(waives, list):
            errors.append(f"{prefix}: 'waives' must be a list")
        else:
            for waived_id in waives:
                if waived_id not in section_ids:
                    errors.append(
                        f"{prefix}: waives unknown section_id '{waived_id}'"
                    )

    # Validate exclusions
    exclusions = data.get("exclusions", [])
    if not isinstance(exclusions, list):
        errors.append("'exclusions' must be a list")

    # Validate tips and reminders are lists
    if "denial_prevention_tips" in data and not isinstance(data["denial_prevention_tips"], list):
        errors.append("'denial_prevention_tips' must be a list")

    if "submission_reminders" in data and not isinstance(data["submission_reminders"], list):
        errors.append("'submission_reminders' must be a list")

    return errors


def compile_policy(policy_text: str, payer: str, cpt_code: str) -> dict:
    """
    Compile a payer policy document into a human-readable checklist.

    This is an index-build-time operation. It does NOT receive patient data
    and has no PHI. Any LLM provider is acceptable; Groq is used by default.

    Args:
        policy_text: Full text of the payer policy document.
        payer:       Payer identifier (e.g. "evicore", "utah_medicaid").
        cpt_code:    CPT code string (e.g. "73721").

    Returns:
        A dict with:
          - "payer": payer identifier
          - "cpt_code": CPT code
          - "checklist_sections": list of requirement sections
          - "exception_pathways": list of exceptions that waive requirements
          - "exclusions": list of hard stop scenarios
          - "denial_prevention_tips": list of common denial reasons
          - "submission_reminders": list of submission notes
          - "_validation_errors": list of validation error strings (empty if valid)
          - "_model": model used for compilation

    The dict is also saved to:
        rag_pipeline/compiled_rules/{payer}_{cpt_code}.json
    """
    logger.info(f"Compiling policy checklist for payer={payer}, cpt_code={cpt_code}")

    # Initialise Groq generator (no PHI — any provider acceptable here)
    generator = MedicalGenerator(provider="groq")
    model_name = generator.model_name

    prompt = _build_prompt(policy_text, payer, cpt_code)

    # Use a high token limit — compiled checklists can be large
    raw_response = generator.generate_answer(
        prompt,
        max_tokens=4096,
        temperature=0.0,
    )

    if not raw_response:
        logger.error("LLM returned an empty response")
        result = {
            "payer": payer,
            "cpt_code": cpt_code,
            "checklist_sections": [],
            "exception_pathways": [],
            "exclusions": [],
            "denial_prevention_tips": [],
            "submission_reminders": [],
            "_validation_errors": ["LLM returned an empty response — no checklist compiled"],
            "_model": model_name,
        }
        _save_result(result, payer, cpt_code)
        return result

    parsed = _extract_json_from_response(raw_response)

    if parsed is None:
        logger.error("Could not parse JSON from LLM response")
        result = {
            "payer": payer,
            "cpt_code": cpt_code,
            "checklist_sections": [],
            "exception_pathways": [],
            "exclusions": [],
            "denial_prevention_tips": [],
            "submission_reminders": [],
            "_validation_errors": [
                "LLM response did not contain parseable JSON",
                f"Raw response (first 500 chars): {raw_response[:500]}",
            ],
            "_model": model_name,
        }
        _save_result(result, payer, cpt_code)
        return result

    # Validate structure
    validation_errors = _validate_output(parsed)

    if validation_errors:
        logger.warning(
            f"Compiled checklist for {payer}/{cpt_code} has {len(validation_errors)} validation error(s). "
            "Human review required before deploying."
        )
        for err in validation_errors:
            logger.warning(f"  - {err}")
    else:
        section_count = len(parsed.get('checklist_sections', []))
        exception_count = len(parsed.get('exception_pathways', []))
        logger.info(
            f"Compiled {section_count} checklist sections and "
            f"{exception_count} exception pathways for "
            f"{payer}/{cpt_code} — no validation errors"
        )

    # Add metadata
    result = {**parsed}
    result["_validation_errors"] = validation_errors
    result["_model"] = model_name

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
