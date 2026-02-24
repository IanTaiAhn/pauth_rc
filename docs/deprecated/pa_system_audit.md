# Prior Authorization System — Critical Audit Report
**Generated:** February 13, 2026  
**Scope:** Diagnostic artifacts (patients 01–10) vs. patient chart data, insurance policy, normalization logic, and rule engine

---

## Executive Summary

The diagnostic artifacts are **partially correct but contain significant systematic errors** that undermine the PA checker's reliability. The most critical issues are: (1) the `clinical_indication` normalization function almost never maps correctly to the payer's approved indication list, causing **every single patient to fail the clinical indication criterion**; (2) the X-ray timing rule silently FAILs any patient whose chart doesn't include an explicit "months_ago" number, even when the X-ray is clearly recent; (3) two patients who explicitly qualify for **exception pathways** (Marcus Webb, Robert Asante) are scored as `LIKELY_TO_DENY` with no exception detected; and (4) the readiness score formula treats all rules as equal weight, meaning the evidence-quality check (always-passing) inflates scores for charts that are genuinely deficient.

---

## Part 1 — Patient-by-Patient Accuracy Review

### Patient 01 — Carlos Mendez
**Artifact verdict:** `NEEDS_REVIEW` / Score 80 / Gap: clinical indication  
**Chart diagnosis:** Positive McMurray's test documented, positive Thessaly test, medial joint line tenderness, suspected medial meniscal tear (ICD-10 M23.202)

**Problems:**
- **Clinical indication FAIL is wrong.** The chart explicitly documents *"McMurray's test: Positive medial rotation (clunk palpable)"* and *"Thessaly test: Positive at 20 degrees."* The policy's approved indications include "Positive McMurray's test." The normalizer in `normalized_custom.py` extracts `clinical_indication` by scanning `evidence_notes` for keyword matches. However, the evidence_notes captured in the artifact are `["left knee pain and swelling x 5 months", "pain rated 8/10", "mechanical 'catching' sensation", "intermittent locking of the knee", "moderate to large effusion"]`. McMurray's/Thessaly results were not placed in `evidence_notes` by the LLM extractor — they were in the physical exam section. The normalizer therefore falls through to `"mechanical symptoms"` (from the catching/locking keywords), which is not on the approved indication list. **The correct `clinical_indication` should be `"positive mcmurray"` or `"meniscal tear"`; both are valid.** This is a false FAIL.
- The artifact correctly passes X-ray (same-day, 0 months ago), PT (8 weeks), and clinical notes (same-day).
- **Verdict should be `LIKELY_TO_APPROVE`** if the indication were extracted correctly.

---

### Patient 02 — Brittany Okafor
**Artifact verdict:** `LIKELY_TO_DENY` / Score 40 / Gaps: X-ray timing, PT, clinical indication  
**Chart:** 2-week symptom duration, ibuprofen 5 days only, no PT, X-ray performed same day but `months_ago` is `null` in raw patient data

**Problems:**
- **X-ray FAIL is partially correct but for the wrong reason.** The X-ray was taken on 01/30/2025 (same day as the visit). `imaging_months_ago` is `null` because the LLM extracted the date but didn't compute relative months. The rule engine fails on `null lte 2`. The FAIL is substantively correct (we can't confirm timing) but the reason is missing data, not truly outdated imaging. Chart says "X-ray Right Knee (01/30/2025)" — the timing is clearly within 60 days.
- **PT FAIL is correct.** Chart explicitly says "Patient declines physical therapy referral."
- **Clinical indication FAIL:** `clinical_indication` is `null` (extracted as "Not found in chart"). Chart does document "McMurray's: Mildly positive medial side." The indication should be `"positive mcmurray"` but again wasn't captured in `evidence_notes`.
- **Score 40 is roughly appropriate** given genuinely missing PT and actual insufficient conservative care duration.

---

### Patient 03 — Marcus Webb
**Artifact verdict:** `LIKELY_TO_DENY` / Score 40  
**Chart:** Acute ACL tear, football practice, non-weight-bearing, Segond fracture on X-ray. **Chart explicitly documents that Exception Section 3 criteria are met** (acute traumatic injury + inability to bear weight + suspected complete ligament rupture).

**This is the most serious error in the entire dataset.** The orchestration router has `exception_applied = None` as a hardcoded placeholder ("TODO: Implement exception pathway detection"). The system is supposed to waive the PT and conservative care requirements entirely. Instead, it fails Marcus Webb on PT (correctly noting none was done), fails on X-ray timing (null months_ago), and fails on clinical indication — and issues `LIKELY_TO_DENY`. The correct answer is **LIKELY_TO_APPROVE under the acute trauma exception.**

**Additional problems:**
- `clinical_indication` is `null` despite evidence notes containing "Unable to bear weight," "Sharp pop," and "football practice injury." The keyword map in `normalize_patient_evidence` has `"traumatic injury": ["trauma", "traumatic", "acute injury", "fall", "accident"]` — but the evidence notes don't contain those exact words. "Football practice" and "sharp pop" should map to traumatic injury but don't. Even if they did, `"traumatic injury"` is not in the approved indications list — the normalizer would need to map it to `"red flag"` or the exception pathway.
- The Segond fracture finding (`"Possible avulsion at lateral tibial plateau (Segond fracture pattern) — highly associated with ACL disruption"`) strongly suggests `red_flags` should have been populated or `clinical_indication` set to a ligament-rupture indicator.

---

### Patient 04 — Tyler Kaminsky
**Artifact verdict:** `NEEDS_REVIEW` / Score 80 / Gap: clinical indication  
**Chart:** 14-year-old, pediatric orthopedic evaluation completed, 8 weeks PT, positive McMurray, open physes on X-ray.

**Problems:**
- **Clinical indication FAIL is wrong** for the same reason as Patient 01. McMurray positive is documented but not in `evidence_notes`. Captured indication is `"mechanical symptoms"` (clicking, locking keywords).
- **Pediatric special population requirement is completely ignored.** Policy Section 2.5(a) requires pediatric orthopedic evaluation for members under 18. The chart documents this was completed by Dr. Huang. The normalized policy rules contain no rule for the pediatric evaluation requirement — `normalize_policy_criteria` does not generate a rule for special populations. The system neither validates this requirement nor gives credit for it being met.
- **Verdict should be `LIKELY_TO_APPROVE`** assuming the clinical indication were captured correctly and the pediatric evaluation requirement were handled.

---

### Patient 05 — Randy Schaefer
**Artifact verdict:** `LIKELY_TO_DENY` / Score 60 / Gaps: X-ray timing, clinical indication  
**Chart:** Worker's compensation case. Chart explicitly notes *"WORKER'S COMPENSATION CLAIM"* and that billing should route through the WC carrier first. Policy Section 4(d) explicitly **excludes** worker's comp injuries.

**Problems:**
- **The WC exclusion is completely missed.** The system should either return a special `EXCLUDED` verdict or flag this as not applicable to the Utah Medicaid PA pathway. Instead it runs normal evaluation and issues a partial deny.
- **X-ray FAIL:** X-ray taken 01/29/2025 (same day), but `months_ago` is `null` again. The prior urgent care X-ray from 12/17/2024 (43 days ago) was also referenced — either X-ray would satisfy the 60-day requirement. Both fail because `months_ago` is `null`.
- **Clinical indication:** `"mechanical symptoms"` (clicking, giving-way) — same systematic issue.
- **Score 60 is misleading** because the case should not be processed through this pathway at all.

---

### Patient 06 — Dorothy Fairbanks
**Artifact verdict:** `NEEDS_REVIEW` / Score 80 / Gap: clinical indication  
**Chart:** 72-year-old, bilateral knee OA, 8 weeks PT, surgical candidacy documented, Medicare + Medicaid dual eligible.

**Problems:**
- **Clinical indication is `null`** in the normalized data even though `clinical_indication: null` is the normalized output. The `evidence_notes` contain `["bilateral knee pain", "right greater than left", "7 months", "modest functional improvement initially", "regression over past 2 months"]` — none of these trigger any keyword in the indication map. The chart documents McMurray positive and suspected meniscal tear in the assessment, but these weren't captured in `evidence_notes`.
- **Age 65+ special population requirement is ignored.** Policy Section 2.5(b) requires surgical candidacy assessment and functional impact documentation. The chart explicitly provides both. The system does not check for this, nor credit it.
- **Verdict should be `LIKELY_TO_APPROVE`** given correct extraction.

---

### Patient 07 — Jasmine Tran
**Artifact verdict:** `LIKELY_TO_DENY` / Score 60 / Gaps: X-ray timing, clinical indication  
**Chart:** Post-operative follow-up at 14 weeks, previous partial meniscectomy 10/15/2024. Chart explicitly documents post-op exception criteria are met (within 6 months of surgery).

**This is the second exception pathway the system completely misses.** Like Patient 03:
- `exception_applied` is hardcoded `null`.
- PT requirement should be waived (post-op exception), but the system credits PT as passing (10 weeks, correct). The real issue is the X-ray timing fail due to `null months_ago` and the clinical indication fail.
- **`clinical_indication` is `"instability"` in the normalized data**, which is correctly extracted from evidence notes. However, `"instability"` is not in the approved indication list (`["meniscal tear", "positive mcmurray", "red flag", "post-operative"]`). Since the patient IS post-operative, the indication should be `"post-operative"` — and the normalizer does have the keyword `"post-op"` in its map. But the `evidence_notes` are `["New onset lateral knee pain", "renewed effusion", "instability on uneven ground"]` — none of these contain "post-op" or "post-surgical." The chart's procedure history section was apparently not captured into `evidence_notes`.
- **Verdict should be `LIKELY_TO_APPROVE` under post-op exception.**

---

### Patient 08 — Robert Asante
**Artifact verdict:** `LIKELY_TO_DENY` / Score 40  
**Chart:** Suspected septic arthritis, fever 102.6°F, WBC 18,400, CRP 14.2, turbid joint aspirate WBC 68,400. Red flag exception explicitly documented. Chart orders MRI **with** contrast (CPT 73722), not without contrast (73721).

**Multiple serious problems:**
- **Wrong CPT code.** The chart orders CPT 73722 (with contrast) for suspected infection/abscess evaluation. The artifact evaluates against CPT 73721 (without contrast). The ordering physician documented contrast is specifically needed to evaluate synovial enhancement and abscess formation. This is a fundamental mismatch.
- **Red flag exception completely missed.** `red_flags.documented = true` in the raw patient data with `description = "fever, elevated WBC/CRP/ESR"`. The normalizer's keyword map for `"red flag": ["infection", "tumor", "fracture", "cancer", "septic"]` should have matched the evidence notes — but `evidence_notes` only contain `["can't walk", "fever to 102.4°F", "unable to bear weight"]`. "Fever" alone doesn't trigger "infection" in the notes text. The `red_flags` field was correctly populated in the raw extraction but the normalizer ignores `red_flags.documented` entirely and only scans `evidence_notes`.
- **PT requirement should be automatically waived** per policy for red flag/infection indications (Section 3.3). Not waived.
- **Verdict should be LIKELY_TO_APPROVE under red flag exception** (if the correct CPT were used).

---

### Patient 09 — Denise Kowalczyk
**Artifact verdict:** `LIKELY_TO_DENY` / Score 60 / Gaps: X-ray timing, clinical indication  
**Chart:** X-ray dated 10/01/2024, which is 118 days (approximately 4 months) before the 01/27/2025 visit. The chart explicitly notes the X-ray is too old and orders a new one. `imaging_months_ago = 4` is correctly extracted.

**Assessment:**
- **X-ray FAIL is correct and well-founded.** The 4-month-old X-ray is genuinely outside the 60-day window. This is the only patient where the X-ray failure is legitimate and accurately captured with a real numeric value (4 months > 2 months threshold).
- **Clinical indication:** `null` — same systematic problem. McMurray positive is documented ("McMurray's: Positive medial side (pain and click)") but not in evidence_notes.
- **The plan documented in the chart** (order new X-ray, then submit PA) means this patient will likely pass once the new X-ray is taken — the system is correctly prompting for action on the right gap.
- **Score 60 is reasonable** given the one genuine gap. Would be higher (80) if clinical indication were correctly extracted.

---

### Patient 10 — Tiffany Osei
**Artifact verdict:** `LIKELY_TO_DENY` / Score 40 / Gaps: X-ray, PT duration, clinical indication  
**Chart:** Repeat MRI within 12 months. Prior MRI 08/14/2024 (5 months ago). Chart documents change in clinical status, new locking episodes, extension block, functional decline.

**Problems:**
- **X-ray FAIL is correct in substance but for the wrong reason.** `imaging_type = "MRI"` and `imaging_months_ago = 5`. The policy requires an X-ray, and what's on file is a prior MRI. The rule correctly fails `imaging_type eq X-ray`. However, the artifact shows `found: "Yes; MRI; 5"` — the system found imaging but it's the wrong type. A current X-ray (01/23/2025) IS referenced in the chart ("X-ray Right Knee (01/23/2025 — within 60 days)"). The LLM extractor apparently captured the prior MRI imaging rather than the recent X-ray. **This is a LLM extraction error, not a genuine gap.**
- **PT FAIL:** `pt_duration_weeks = null`. Chart says PT was continued post-prior-MRI but duration isn't explicitly restated for this visit period. The LLM captured PT as attempted but without duration. Given the history of prior PT completing 6+ weeks, this is another extraction gap.
- **Repeat MRI 12-month rule is completely unhandled.** Policy Section 4(f) has specific criteria for repeat imaging within 12 months (change in clinical status, failed intervention, pre-op planning). The chart documents all three criteria. The system has no rule to evaluate this — nor does it give credit for meeting the repeat imaging justification.
- **Clinical indication:** `"mechanical symptoms"` from locking/giving-way keywords, but `"meniscal tear"` should be the indication (Grade 2 radial tear is on record; current locking suggests displacement).

---

## Part 2 — Systematic Issues Across All Patients

### Issue 1: `clinical_indication` Normalization is Fundamentally Broken

**Severity: Critical**

Every single patient fails the `clinical_indication_requirement`. The root cause is a design flaw in `normalize_patient_evidence()`:

The function scans `evidence_notes[]` for keywords. But `evidence_notes` is populated by the LLM extractor with brief verbatim quotes about symptoms (pain levels, swelling, duration). Physical examination findings like "McMurray positive" almost never appear in `evidence_notes` because the LLM places them in the structured `pain_characteristics`, `imaging.findings`, or other schema fields instead.

The normalizer should also scan `imaging.findings`, the structured exam fields, and the `red_flags.description` field — not only `evidence_notes`. Alternatively, the LLM extraction prompt should be updated to require exam findings in `evidence_notes`.

Additionally, the indication keyword → approved-indication mapping is incomplete:
- `"meniscal tear"` maps correctly, but only if that exact phrase appears in evidence notes.
- `"positive mcmurray"` is in the approved list but the keyword scan looks for `"mcmurray"` in evidence_notes — which is rarely there.
- `"traumatic injury"` is a normalizer output but is NOT in the approved indications list. The normalizer and the approved list are out of sync.
- `"instability"` is a normalizer output but is NOT in the approved indications list.
- `"mechanical symptoms"` is a normalizer output but is NOT in the approved indications list.
- The approved indications should include `"mechanical symptoms"` since Policy Section 2.1 explicitly lists *"Knee pain with mechanical symptoms — locking, catching, giving way (ICD-10: M25.561)"* as an eligible diagnosis under Category A.

### Issue 2: `imaging_months_ago = null` Causes Silent FAIL for Recent X-rays

**Severity: High**

5 of 10 patients have `imaging_months_ago = null` (patients 02, 03, 05, 07, 08). In every case the X-ray was clearly taken the same day or within the required window — but the LLM extractor didn't compute a relative month count. The rule engine fails `null lte 2`, issuing a FAIL even when the imaging is current.

The fix is straightforward: if `clinical_notes_date` is available and `imaging.type` is documented, compute `imaging_months_ago` from `clinical_notes_date` minus the imaging date. The raw extraction includes `imaging_months_ago: 0` when the X-ray was taken the same day as the note — but for patients where the imaging section doesn't include an explicit relative reference, the value is null.

For Patient 02 in particular: the raw patient data shows `months_ago: null` but the chart date is 01/30/2025 and the X-ray date is also 01/30/2025. This should be `0`, not `null`.

### Issue 3: Exception Pathway Detection is Hardcoded `null`

**Severity: Critical**

In `orchestration.py` line:
```python
# TODO: Implement exception pathway detection
# For now, this is a placeholder
exception_applied = None
```

Three patients (03-Marcus Webb, 07-Jasmine Tran, 08-Robert Asante) explicitly meet documented exception criteria from Policy Section 3:
- Patient 03: Acute trauma exception (Section 3.1)
- Patient 07: Post-operative exception (Section 3.2)
- Patient 08: Red flag exception (Section 3.3)

All three receive `LIKELY_TO_DENY` verdicts that are clinically incorrect. The exception detection logic needs to check `raw_patient` fields: `red_flags.documented`, the presence of acute trauma indicators, or post-op references before applying standard conservative care requirements.

### Issue 4: Readiness Score Inflation from Evidence Quality Rule

**Severity: Medium**

The readiness score is `rules_met / total_rules * 100`. Since there are always 5 rules and the `evidence_quality` rule always passes (0 hallucinations, validation passed), the minimum possible score is 20 (1/5). Every patient with 2 rules met gets 40, and 3 rules met gets 60. But the evidence quality rule is an internal data hygiene check — it has nothing to do with payer clinical criteria. A patient with genuinely terrible documentation still gets 20 points just for having clean extraction metadata. This inflates scores and distorts the verdict thresholds.

### Issue 5: Special Population Rules Are Not Evaluated

**Severity: Medium**

The `normalize_policy_criteria` function generates no rules for Policy Section 2.5 (special populations). Patient 04 (Tyler, age 14) requires pediatric orthopedic evaluation. Patient 06 (Dorothy, age 72) requires surgical candidacy assessment. Both are documented in the charts. The system neither checks for these requirements nor gives credit when they're met. For a real PA submission, missing the pediatric evaluation would cause a denial.

### Issue 6: Worker's Compensation Exclusion Not Detected

**Severity: High**

Patient 05 (Randy Schaefer) is explicitly a workers' comp case. Policy Section 4(d) states MRI is NOT covered under Utah Medicaid for WC injuries — WC carrier must be billed first. The system runs full standard evaluation and returns `LIKELY_TO_DENY` with actionable gaps, implicitly suggesting the provider should fix the documentation and resubmit to Medicaid. This is wrong clinical guidance — the case should be flagged as WC-excluded.

### Issue 7: Repeat Imaging 12-Month Rule Not Implemented

**Severity: Medium**

Patient 10 (Tiffany Osei) has a prior MRI within 12 months. Policy Section 4(f) requires that repeat imaging within 12 months document: (a) change in clinical status, (b) failed intervention, or (c) pre-operative planning. The chart documents all three. The system has no rule for this — it neither requires the documentation nor gives credit for it. The `normalize_policy_criteria` function doesn't extract quantity limits into evaluable rules.

### Issue 8: CPT Code Mismatch for Patient 08

**Severity: High**

Patient 08's chart orders CPT 73722 (with contrast, required for infection/abscess evaluation). The diagnostic artifact evaluates CPT 73721 (without contrast). The payer and CPT in the artifact are both `73721`. Either the CPT code selection step (which should be part of the orchestration) defaulted to 73721, or this was a test data setup error. The contrast safety documentation requirements (eGFR, allergy screening) from Policy 73722 are not evaluated at all.

### Issue 9: `normalized_patient.clinical_indication` vs. `normalized_policy` Approved List Mismatch

**Severity: High**

Cross-referencing the normalizer output values against the policy rule conditions:

| Normalizer can output | In approved list? |
|---|---|
| `meniscal tear` | ✅ Yes |
| `mechanical symptoms` | ❌ No — but IS a valid diagnosis per Policy 2.1 |
| `ligament rupture` | ❌ No |
| `instability` | ❌ No — but IS a valid clinical finding per Policy 2.2(e) |
| `traumatic injury` | ❌ No |
| `positive mcmurray` | ✅ Yes |
| `post-operative` | ✅ Yes |
| `red flag` | ✅ Yes |

The normalizer can produce 4 values that will always fail the policy check, even when the clinical situation genuinely qualifies. `mechanical symptoms` in particular should be added to the approved list since it maps directly to ICD-10 M25.561 in the policy's eligible diagnosis section.

### Issue 10: `normalized_custom.py` Ignores Structured Fields for Clinical Indication

The `normalize_patient_evidence` function's `clinical_indication` extraction reads only `evidence_notes`. It should also check:
- `pain_characteristics.quality` (e.g., `"mechanical 'catching' sensation"`)
- `red_flags.documented` and `red_flags.description`
- `imaging.findings` for terms like "meniscal tear"
- The raw assessment/diagnosis section (if captured)

---

## Part 3 — Policy Extraction Accuracy

The RAG pipeline appears to be extracting the correct structural criteria from the three Utah Medicaid policy files (73721, 73722, 73723). The `normalized_policy.rules` across all 10 artifacts consistently show the same 5 rules:
1. X-ray within 60 days ✅ Correct per Policy 2.3
2. PT minimum 6 weeks ✅ Correct per Policy 2.4(a)
3. Clinical notes within 30 days ✅ Correct per Policy 5
4. Clinical indication (from Section 2.1/2.2) ✅ Partially correct (list is incomplete/misaligned)
5. Evidence quality (internal) — not from policy

**What the policy extraction misses:**
- Section 3 exception pathways (acute trauma, post-op, red flags) — not converted to rules
- Section 2.5 special population requirements — not converted to rules
- Section 4(d) worker's compensation exclusion — not captured
- Section 4(f) repeat imaging within 12 months — not converted to a rule
- The `quantity_limits` field is captured in `raw_policy` but never converted to an evaluable rule

One minor note: some artifacts show `"red flag"` appearing twice in the condition value list (e.g., `["meniscal tear", "positive mcmurray", "red flag", "red flag", "post-operative"]`). This is a deduplication bug in `normalize_policy_criteria` — the indication `"Infection with abscess concern"` and tumor/red-flag indications both map to `"red flag"`, causing duplicates.

---

## Part 4 — Score Accuracy Summary

| Patient | Artifact Score | Correct Verdict | Artifact Verdict | Assessment |
|---|---|---|---|---|
| 01 Mendez | 80 | LIKELY_TO_APPROVE | NEEDS_REVIEW | **Wrong** — clinical indication is false FAIL |
| 02 Okafor | 40 | LIKELY_TO_DENY | LIKELY_TO_DENY | **Correct verdict**, X-ray reason is extraction gap |
| 03 Webb | 40 | LIKELY_TO_APPROVE (exception) | LIKELY_TO_DENY | **Wrong** — exception not detected |
| 04 Kaminsky | 80 | LIKELY_TO_APPROVE | NEEDS_REVIEW | **Wrong** — clinical indication is false FAIL |
| 05 Schaefer | 60 | WC-EXCLUDED | LIKELY_TO_DENY | **Wrong** — WC exclusion not flagged |
| 06 Fairbanks | 80 | LIKELY_TO_APPROVE | NEEDS_REVIEW | **Wrong** — clinical indication is false FAIL |
| 07 Tran | 60 | LIKELY_TO_APPROVE (exception) | LIKELY_TO_DENY | **Wrong** — post-op exception not detected |
| 08 Asante | 40 | LIKELY_TO_APPROVE (exception, wrong CPT) | LIKELY_TO_DENY | **Wrong** — red flag exception + CPT mismatch |
| 09 Kowalczyk | 60 | NEEDS_REVIEW (legit X-ray gap) | LIKELY_TO_DENY | **Approximately correct** |
| 10 Osei | 40 | NEEDS_REVIEW | LIKELY_TO_DENY | **Wrong** — X-ray extraction error, repeat MRI rule missing |

**Score accuracy: 1–2 out of 10 patients evaluated correctly.** The system is failing primarily because of the clinical indication normalization bug, not because the policy criteria themselves are incorrectly defined.

---

## Priority Fix List

1. **[Critical]** Fix `clinical_indication` extraction — scan `imaging.findings`, `pain_characteristics.quality`, `red_flags.description`, and the raw assessment in addition to `evidence_notes`. Add `"mechanical symptoms"` and `"instability"` to the approved indication list.
2. **[Critical]** Implement exception pathway detection in `orchestration.py` — check `red_flags.documented`, `functional_impairment_description` for "unable to bear weight," and `conservative_therapy` context before evaluating standard PA rules.
3. **[High]** Fix `imaging_months_ago = null` — compute from `clinical_notes_date` minus imaging date when the LLM doesn't provide a relative count.
4. **[High]** Add WC exclusion detection — check for WC claim language in the extracted patient data.
5. **[Medium]** Add special population rules to `normalize_policy_criteria` — at minimum flag under-18 pediatric evaluation and 65+ surgical candidacy requirements.
6. **[Medium]** Add repeat imaging 12-month rule — extract from `quantity_limits` in the policy and create a conditional rule.
7. **[Medium]** Remove `evidence_quality` rule from the readiness score denominator, or weight it at 0 for scoring purposes since it is an internal check, not a payer criterion.
8. **[Low]** Deduplicate the approved indication list in `normalize_policy_criteria` to fix the `"red flag"` duplication.
