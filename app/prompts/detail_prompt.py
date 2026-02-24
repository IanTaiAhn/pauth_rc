"""
Prompt builder for Step 2: skeleton + policy → filled checklist.

The LLM fills in specifics into the existing structure.
It does NOT change the structure — only extracts details into slots.
"""

import json


def build_detail_prompt(policy_text: str, skeleton: dict) -> str:
    skeleton_json = json.dumps(skeleton, indent=2)
    return f"""You are a medical policy analyst. A checklist skeleton has already been built from this policy.
Your job is to fill in the details — do NOT change the structure.

For each section and item in the skeleton, add:
- help_text: specific, actionable guidance for billing staff
- icd10_codes: list of ICD-10 codes if the policy references specific diagnoses (else omit)
- detail_fields: nested fields for "checkbox_with_detail" items (else omit)

Also fill in the top-level fields:
- policy_source: document title and section reference
- policy_effective_date: YYYY-MM-DD or null

And add:
- denial_prevention_tips: list of specific denial reasons with concrete documentation advice
- submission_reminders: list of important PA submission notes (authorization validity, required documents, decision timelines)

SKELETON (structure is locked — do not add, remove, or rename sections or items):
{skeleton_json}

Take the skeleton above and return it fully filled in as valid JSON.
Copy the structure exactly. Only add the detail fields listed above.
Output ONLY the JSON — no markdown fences, no commentary.

---
POLICY DOCUMENT:
{policy_text}
---

JSON OUTPUT:"""
