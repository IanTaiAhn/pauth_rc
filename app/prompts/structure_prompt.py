"""
Prompt builder for Step 1: policy → checklist skeleton.

The LLM focuses only on logic and structure — not on extracting details.
"""


def build_structure_prompt(policy_text: str, payer: str, cpt_code: str) -> str:
    return f"""You are a medical policy analyst. Your task is to identify the LOGICAL STRUCTURE of this prior authorization policy.

Do NOT extract specific details (ICD-10 codes, exact timeframes, documentation requirements) yet.
Focus ONLY on:
- What sections/categories of requirements exist
- Whether each section requires ANY item, ALL items, or at least N items (count_gte)
- What exception pathways exist and which sections they waive
- What exclusion scenarios exist

Payer: {payer}
CPT Code: {cpt_code}

Output ONLY valid JSON with this exact structure:

{{
  "checklist_sections": [
    {{
      "id": "snake_case_section_id",
      "title": "Human-Readable Section Title",
      "description": "One sentence: what this section requires in plain English",
      "requirement_type": "any | all | count_gte",
      "threshold": 2,
      "items": [
        {{
          "field": "snake_case_field_name",
          "label": "Short label (1-8 words)",
          "input_type": "checkbox | date | number | text | checkbox_with_detail"
        }}
      ]
    }}
  ],
  "exception_pathways": [
    {{
      "id": "exception_snake_case_id",
      "title": "Exception Title",
      "description": "What this exception covers",
      "waives": ["section_id_1", "section_id_2"],
      "requirement_type": "any | all | count_gte",
      "threshold": null,
      "items": [
        {{
          "field": "field_name",
          "label": "Label",
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
  ]
}}

Rules:
- requirement_type meanings:
  * "any" = at least ONE item must be met
  * "all" = ALL items must be met
  * "count_gte" = at least `threshold` items must be met
- Only include "threshold" when requirement_type is "count_gte"
- "waives" must list section IDs from checklist_sections
- Use snake_case for all IDs and field names
- Output ONLY the JSON — no markdown fences, no commentary

---
POLICY DOCUMENT:
{policy_text}
---

JSON OUTPUT:"""
