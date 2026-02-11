Newly generated patient info fails when attempting to extract via groq llm:

patient_02_fail_insufficient_conservative.txt --> 
{
  "detail": "Error processing file: '>' not supported between instances of 'NoneType' and 'int'"
}

patient_03_exception_acute_acl
{
  "detail": "Error processing file: '>' not supported between instances of 'NoneType' and 'int'"
}

patient_05_workerscomp_exclusion
{
  "detail": "Error processing file: 1 validation error for InitialPatientExtraction\nmissing_items.0\n  Input should be a valid string [type=string_type, input_value={'name': 'symptom_duratio... of at least 3 months.'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.12/v/string_type"
}

patient_07_exception_post_surgical
{
  "detail": "Error processing file: 2 validation errors for InitialPatientExtraction\nmissing_items.0\n  Input should be a valid string [type=string_type, input_value={'name': 'symptom_duratio... of at least 3 months.'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.12/v/string_type\nmissing_items.1\n  Input should be a valid string [type=string_type, input_value={'name': 'conservative_th..., NSAIDs, injections).'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.12/v/string_type"
}

patient_08_exception_red_flag_infection
{
  "detail": "Error processing file: '>' not supported between instances of 'NoneType' and 'int'"
}

patient_10_repeat_mri_change_in_status
{
  "detail": "Error processing file: '>=' not supported between instances of 'NoneType' and 'int'"
}


Manual api steps are too hard. Need to reimagine how a clinician will use this tool:

Step 1:  "Here is my patient's chart(s)"     →  [upload file]
Step 2:  "Which insurance, which MRI?"    →  [two dropdowns]
                    ↓
         [single button: "Check Prior Auth"]
                    ↓
         PA Readiness Report   ←  this is all they ever see

The full UX flow in detail:
Screen 1 — New PA Check
A single clean form:

Patient chart: drag-and-drop upload zone (PDF or scanned document). "Drop chart note here or click to upload."
Payer: dropdown — Aetna / Utah Medicaid / United / etc. (you only have one right now, which is fine — it just shows one option)
Procedure requested: dropdown — "Knee MRI (no contrast) — 73721" / "Knee MRI (with contrast) — 73722" / "Knee MRI (without/with contrast) — 73723". Plain English labels, CPT codes secondary.
One button: "Run PA Check"

That's the entire input surface.
Screen 2 — Processing (10-15 seconds)
A simple progress indicator with honest status messages:

"Reading chart..." (ingestion + extraction)
"Checking Aetna knee MRI criteria..." (RAG + normalization)
"Comparing clinical evidence..." (rule engine)

Clinicians in a busy practice will tolerate 15 seconds if they understand what's happening.
Screen 3 — The Report
This is the actual product. Three zones:
Zone A — The verdict (top, big)
✅ LIKELY TO APPROVE          or          ❌ LIKELY TO DENY
   Readiness Score: 87%                      Readiness Score: 41%
Zone B — Why (the most valuable part)
A checklist of every criterion the payer requires, with clear pass/fail for each:
✅  Conservative care completed       8 weeks PT (required: 6)
✅  Physical therapy documented       24 sessions on file
✅  NSAIDs trial documented           8 weeks naproxen
✅  X-ray within 60 days              Performed 01/28/2025
✅  Positive clinical findings        McMurray positive, effusion
❌  Corticosteroid injection          Not documented
⚠️  Imaging recency                  X-ray is 58 days old — recheck before submission
This is the table your rule engine already produces. You just need to render it.
Zone C — What to do next
If denied or borderline, specific actionable text:

"Before submitting, document: (1) corticosteroid injection date and response, or explicitly note it was contraindicated. This is the only unmet criterion."

If approved:

"This chart meets all criteria for CPT 73721. You can submit the PA now. Download the summary report to attach to your submission."

A Download Report button produces a PDF they can attach to the actual PA submission.

This is the table your rule engine already produces. You just need to render it.
Zone C — What to do next
If denied or borderline, specific actionable text:

"Before submitting, document: (1) corticosteroid injection date and response, or explicitly note it was contraindicated. This is the only unmet criterion."

If approved:

"This chart meets all criteria for CPT 73721. You can submit the PA now. Download the summary report to attach to your submission."

A Download Report button produces a PDF they can attach to the actual PA submission.

