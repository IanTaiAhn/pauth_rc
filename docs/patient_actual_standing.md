# Patient Results vs. Reality — P-Auth RC Test Suite Analysis

> **Payer:** Utah Medicaid · **CPT:** 73721 (MRI Knee Without Contrast) · **Date:** February 2026

---

## Summary Table

| Patient | Final Best Score | Verdict | Correct? | Key Issue If Wrong |
|---|---|---|---|---|
| Carlos Mendez | 100 (v1.3) | LIKELY_TO_APPROVE | ✅ Yes | Fixed by indication mapping |
| Brittany Okafor | 75 (v2.1) | NEEDS_REVIEW | ⚠️ Mostly | "red flag" indication assignment is wrong, but PT FAIL is correct |
| Marcus Webb | 25 w/ exception (v3) | LIKELY_TO_APPROVE | ⚠️ Score misleading | Exception should adjust score to reflect override |
| Tyler Kaminsky | 100 (v4.4) | LIKELY_TO_APPROVE | ✅ Yes | Required 3 iterations to stabilize |
| Randy Schaefer | 0 (v5) | EXCLUDED | ✅ Yes | WC detection works correctly |
| Dorothy Fairbanks | 75 (v6.1, v6.2) | NEEDS_REVIEW | ❌ No — should be higher | Positive McMurray's not reaching the indication mapper |
| Jasmine Tran | 100 (v7.3) | LIKELY_TO_APPROVE | ✅ Yes | Fixed by completeness check + indication mapping |
| Robert Asante | 50 w/ exception (v8) | LIKELY_TO_APPROVE | ⚠️ Score misleading | Same exception scoring issue as Marcus Webb |
| Denise Kowalczyk | 50 (v9.1, v9.2) | LIKELY_TO_DENY | ⚠️ Partially | X-ray gap is correct; indication gap is a false failure |
| Tiffany Osei | 50 (v10.3) | LIKELY_TO_DENY | ✅ Yes — real gaps exist | Repeat imaging warning adds clinical value |

---

## Patient-by-Patient Detail

### 1. Carlos Mendez — ✅ Correct (after fix)

- **Chart reality:** 53 y/o male, 5 months left knee pain, positive McMurray's, mechanical catching/locking, 8 weeks PT completed, recent X-ray, suspected meniscal tear.
- **v1.2 result:** Score 75 — FAIL on clinical indication (`"mechanical symptoms"` not in policy allowlist).
- **v1.3 result:** Score 100 — `_map_clinical_indication()` now maps mechanical keywords in evidence notes to `"meniscal tear"`.
- **Assessment:** The fix is correct. This chart clearly meets Utah Medicaid Section 2.1 Category A criteria.

### 2. Brittany Okafor — ⚠️ Mostly Correct

- **Chart reality:** 30 y/o female, 2 weeks of symptoms, 5 days PRN ibuprofen only, no PT attempted, declined PT referral. Provider's own note says PA cannot be submitted yet.
- **v2.1 result:** Score 75 — FAIL on PT requirement. PASS on clinical indication with `"red flag"`.
- **Assessment:** The PT failure is correct — this patient hasn't met the 6-week conservative care requirement. However, the system assigns `"red flag"` as the clinical indication, which is wrong. Nothing in this chart suggests infection, tumor, or fracture. She has a mild sports injury with a mildly positive McMurray's. The `"red flag"` assignment likely comes from keyword matching that's too aggressive. The correct indication would be `"positive mcmurray"` or `"meniscal tear"`. The final verdict (NEEDS_REVIEW) is appropriate despite the misclassification.

### 3. Marcus Webb — ⚠️ Score Misleading

- **Chart reality:** 23 y/o male, acute ACL rupture from football injury. Lachman 3+, positive pivot shift, Segond fracture pattern on X-ray, hemarthrosis, non-weight-bearing. Textbook acute trauma exception (Policy Section 3.1).
- **v3 exception result:** Verdict LIKELY_TO_APPROVE, but score is only 25 (3 of 5 standard rules fail).
- **v3.3 result (no exception):** Score 50 — FAIL on PT (not attempted, expected for acute injury) and clinical indication (`null`).
- **Assessment:** The exception detection works correctly — acute trauma with inability to bear weight and suspected complete ligament rupture triggers Section 3.1. The problem is that the readiness score (25) doesn't reflect the exception override. A clinic user seeing "LIKELY_TO_APPROVE" at score 25 will be confused. The scoring model needs to account for exception pathways.

### 4. Tyler Kaminsky — ✅ Correct (after 3 iterations)

- **Chart reality:** 14 y/o male, 3 months right knee pain, positive McMurray's at 90°, clicking with squatting, 8 weeks PT, recent X-ray, pediatric orthopedic evaluation completed.
- **v4.2 result:** Score 75 — FAIL on clinical indication (`"mechanical symptoms"`).
- **v4.3 result:** Score 75 — FAIL on clinical indication (`null` — evidence notes didn't include mechanical keywords this run).
- **v4.4 result:** Score 100 — all criteria pass, indication correctly mapped to `"meniscal tear"`.
- **Assessment:** The final result is correct but required 3 runs to stabilize, exposing LLM extraction variance. The underlying clinical data is identical across runs — only the LLM's text selection into `evidence_notes` changed. Note: the pediatric special population requirement (Section 2.5a) is detected but not evaluable because `patient_age` isn't in the normalized schema yet.

### 5. Randy Schaefer — ✅ Correct

- **Chart reality:** 46 y/o male, workplace fall injury, active WC claim (WC-2025-UT-00441), State Insurance Fund of Utah as WC carrier.
- **v5 result:** EXCLUDED, score 0.
- **Assessment:** Workers' compensation detection correctly identifies the WC case from evidence notes ("workplace fall") and functional impairment ("modified duty"). The system correctly cites Policy Section 4(d) and directs billing to the WC carrier. This is the cleanest result in the test suite.

### 6. Dorothy Fairbanks — ❌ Incorrect

- **Chart reality:** 72 y/o female, 7 months bilateral knee pain, positive McMurray's, mechanical locking, severe medial OA (Grade 3/4), 8 weeks PT, recent X-ray, surgical candidate with functional impact assessment completed.
- **v6.1 and v6.2 result:** Score 75 — FAIL on clinical indication (`null` / "Not found in chart").
- **Assessment:** This is a false failure. The chart documents positive McMurray's test, which is explicitly listed in Policy Section 2.2(a). It also documents OA requiring surgical planning (Policy Section 2.1 Category B). The `_map_clinical_indication()` function misses these because: (1) "mcmurray" doesn't appear in `evidence_notes` (only in the structured exam section), and (2) the function doesn't check for OA + surgical candidacy as a valid pathway. Additionally, the age 65+ special population requirements (Section 2.5b) are detected but not evaluable. With the indication fix, this patient should score 100.

### 7. Jasmine Tran — ✅ Correct (after fix)

- **Chart reality:** 36 y/o female, 14 weeks post partial medial meniscectomy, new lateral knee pain and effusion, positive McMurray's lateral side, instability on uneven ground. Meets post-operative exception (Section 3.2).
- **v7.2 result:** Score 50 — FAIL on X-ray timing (`imaging_months_ago: null`) and clinical indication (`"instability"`).
- **v7.3 result:** Score 100 — completeness check auto-calculates `imaging_months_ago: 0`, indication maps from instability to `"meniscal tear"`.
- **Assessment:** Both fixes are correct. The completeness check resolves the null imaging date, and the indication mapping correctly identifies that new lateral symptoms in a post-meniscectomy patient warrant meniscal tear evaluation. The post-operative exception is also available but not needed since all standard criteria pass.

### 8. Robert Asante — ⚠️ Score Misleading

- **Chart reality:** 59 y/o male, suspected septic arthritis. Fever 102.6°F, WBC 18,400, CRP 14.2, turbid joint aspirate with 68,400 WBC. Unable to bear weight. No PT or conservative care (not applicable for acute infection). Red flag exception (Policy Section 3.3).
- **v8 exception result:** Verdict LIKELY_TO_APPROVE, score 50 (2 standard rules fail: X-ray timing null, no PT).
- **Assessment:** The red flag exception detection works correctly — fever, elevated inflammatory markers, and turbid aspirate trigger Section 3.3. As with Marcus Webb, the score doesn't reflect the exception override. Additionally, the chart actually orders CPT 73722 (with contrast) for infection evaluation, but the system evaluates against 73721 criteria. The system correctly identifies the clinical urgency but the numeric score is misleading.

### 9. Denise Kowalczyk — ⚠️ Partially Correct

- **Chart reality:** 45 y/o female, 6 months left knee pain, positive McMurray's with pain and click, 8 weeks PT, corticosteroid injection, X-ray from 4 months ago (too old — provider notes this explicitly).
- **v9.1 and v9.2 result:** Score 50 — FAIL on X-ray timing (4 months > 2 month limit) and clinical indication (`null`).
- **Assessment:** The X-ray timing failure is correct — the provider's own chart note acknowledges the X-ray is 118 days old and orders a repeat. This is the system working as intended. However, the clinical indication failure is wrong for the same reason as Dorothy Fairbanks: positive McMurray's is documented in the structured exam but doesn't reach the mapper. With the indication fix, this patient would correctly score 75 (one real gap: outdated X-ray), which matches the provider's own assessment.

### 10. Tiffany Osei — ✅ Correct

- **Chart reality:** 41 y/o female, prior MRI from 5 months ago showing Grade 2 radial meniscal tear. Now with new locking episodes, giving-way, extension block, significant functional decline. Requesting repeat MRI with documented change in clinical status.
- **v10.1 result:** Score 25 — FAIL on X-ray (only has MRI, no X-ray), PT duration (`null`), and clinical indication (`"mechanical symptoms"`).
- **v10.2 result:** Score 50 — indication improves to `"meniscal tear"` via mapping. X-ray and PT duration still fail.
- **v10.3 result:** Score 50 — adds repeat imaging warning: "Review existing MRI from 5 month(s) ago before ordering a new study."
- **Assessment:** The failures are real. The patient has no recent X-ray (only a 5-month-old MRI), and PT duration is undocumented. The repeat imaging warning is clinically valuable — it prompts review of existing imaging before ordering a new $1,500+ study. The change-in-clinical-status documentation is strong (new locking, extension block, functional decline), but the system can't yet evaluate the repeat imaging justification criteria from Policy Section 4(f).

---

## Systemic Issues Identified

| Issue | Severity | Affected Patients | Status |
|---|---|---|---|
| Clinical indication mapping too narrow (mechanical symptoms, instability) | 🔴 Critical | 01, 04, 07, 10 | **Fixed** via `_map_clinical_indication()` |
| McMurray's positive not reaching mapper from structured exam data | 🔴 Critical | 06, 09 | **Open** |
| Exception pathways don't adjust readiness score | 🟠 High | 03, 08 | **Open** |
| LLM extraction variance between runs | 🟠 High | 04 (3 runs to stabilize) | **Open** — inherent LLM non-determinism |
| PT duration inconsistently extracted from RAG policy output | 🟡 Medium | 04 | **Partially fixed** via `_validate_policy_consistency()` |
| `imaging_months_ago` null when same-day imaging not calculated | 🟡 Medium | 07, 08 | **Fixed** via completeness check + default-to-0 |
| Special population rules (age <18, age 65+) detected but not evaluable | 🟡 Medium | 04, 06 | **Open** — needs `patient_age` field |
| Repeat imaging 12-month justification not fully evaluable | 🟡 Medium | 10 | **Partially fixed** — warning issued, criteria not evaluated |
| Brittany Okafor incorrectly assigned "red flag" indication | 🟡 Medium | 02 | **Open** |