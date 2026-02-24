# Checklist Review: Utah Medicaid 73721 (MRI Knee No Contrast)

**Review Date:** 2026-02-23
**Source Policy:** `utah_medicaid_73721_mri_knee_no_contrast.txt`
**Compiled Checklist:** `api_artifacts/policy_json_02_23.json`
**Compiler Model:** llama-3.3-70b-versatile
**Overall Score:** 7.5/10

---

## Executive Summary

The LLM compiler did a **good job** capturing the overall structure and most requirements, but has **one critical error** and several areas needing human refinement before production deployment. The core architecture works well - this demonstrates the expected "LLM draft → human curation" workflow.

---

## ❌ CRITICAL ISSUES (Must Fix Before Production)

### Issue #1: Conservative Treatment Requirement Type - WRONG

**Severity:** CRITICAL
**Location:** `checklist_sections[3]` - "Conservative Treatment Requirement"

**Problem:**
The policy explicitly states **"at least TWO of the following 5 treatments"**, but the compiled checklist uses `requirement_type: "all"` which requires ALL 5 treatments to be checked.

**Source Policy Evidence (lines 86-88):**
```
Member must have completed a minimum of SIX WEEKS (42 consecutive calendar days)
of conservative therapy. Documentation must reflect completion of at least
TWO of the following treatment modalities:
```

**Current (WRONG):**
```json
{
  "id": "conservative_treatment_requirement",
  "requirement_type": "all",  // ❌ Requires ALL 5 - incorrect
  "items": [
    { "field": "physical_therapy", ... },
    { "field": "non_steroidal_anti_inflammatory_drugs", ... },
    { "field": "activity_modification", ... },
    { "field": "bracing_orthotics_or_assistive_devices", ... },
    { "field": "intra_articular_injection", ... }
  ]
}
```

**Required Fix:**
```json
{
  "id": "conservative_treatment_requirement",
  "requirement_type": "count_gte",  // ✅ At least 2 of 5
  "threshold": 2,                   // ✅ Add threshold
  "help_text": "Document at least 2 of the following 5 treatments. Total duration must be at least 6 weeks (42 days). Multiple treatments may be done concurrently.",
  "items": [ /* same 5 items */ ]
}
```

**Impact:** Without this fix, the checklist would require clinics to document ALL 5 treatment modalities when the policy only requires 2. This would cause incorrect denials and frustration.

---

## ⚠️ HIGH PRIORITY ISSUES (Should Fix)

### Issue #2: Missing Special Populations Section

**Severity:** HIGH
**Location:** Missing from `checklist_sections`

**Problem:**
The policy has specific requirements for two age groups (lines 108-121 of source policy), but these were completely omitted from the checklist.

**Source Policy Evidence:**

**Section 2.5(a) - Members Under Age 18:**
- Pediatric orthopedic evaluation by board-certified/board-eligible pediatric orthopedic surgeon required
- Growth plate (physeal) assessment must be included

**Section 2.5(b) - Members Age 65 and Older:**
- Documentation of functional impact on ADLs required
- Assessment of surgical candidacy required
- If not a surgical candidate, MRI only covered if results will change non-surgical management

**Required Fix:**
Add a new checklist section:

```json
{
  "id": "special_population_requirements",
  "title": "Special Population Requirements",
  "description": "Additional requirements for specific age groups",
  "requirement_type": "any",
  "help_text": "If the member is under 18 OR 65+, check the applicable section",
  "items": [
    {
      "field": "pediatric_requirements",
      "label": "Member under 18 - Pediatric orthopedic evaluation",
      "help_text": "Required: Evaluation by board-certified or board-eligible pediatric orthopedic surgeon, including growth plate assessment. Include evaluation documentation with PA.",
      "input_type": "checkbox_with_detail",
      "detail_fields": [
        {
          "field": "pediatric_eval_date",
          "label": "Evaluation date",
          "input_type": "date"
        },
        {
          "field": "evaluating_surgeon",
          "label": "Pediatric orthopedic surgeon name",
          "input_type": "text"
        }
      ]
    },
    {
      "field": "geriatric_requirements",
      "label": "Member 65+ - Surgical candidacy assessment",
      "help_text": "Required: Document functional impact on ADLs and whether member is a surgical candidate. If NOT a surgical candidate, must document how MRI will directly modify non-surgical management plan.",
      "input_type": "checkbox_with_detail",
      "detail_fields": [
        {
          "field": "surgical_candidate",
          "label": "Is member a surgical candidate?",
          "input_type": "text"
        },
        {
          "field": "functional_impact",
          "label": "Describe functional impact on ADLs",
          "input_type": "text"
        }
      ]
    },
    {
      "field": "standard_adult_population",
      "label": "Member age 18-64 (standard population)",
      "help_text": "No special requirements for this age group",
      "input_type": "checkbox"
    }
  ]
}
```

**Impact:** Pediatric and geriatric cases would be submitted without required documentation, leading to denials.

---

### Issue #3: Prior Imaging Section Structure - Confusing

**Severity:** MEDIUM
**Location:** `checklist_sections[2]` - "Prior Imaging Requirement"

**Problem:**
The section lists 3 separate checkbox items with `requirement_type: "all"`, making it seem like 3 distinct requirements. In reality, it's one requirement: "X-rays completed within 60 days, with report available."

**Current Structure:**
```json
{
  "requirement_type": "all",
  "items": [
    { "field": "x_ray_report", "label": "X-ray Report" },
    { "field": "weight_bearing_ap_view", "label": "Weight-Bearing AP View" },
    { "field": "radiograph_report_available", "label": "Radiograph Report Available" }
  ]
}
```

**Issues:**
- Items 1 and 3 are redundant (both ask if report is available)
- Doesn't capture "within 60 days" requirement
- Weight-bearing contraindication scenario not handled

**Recommended Fix:**
```json
{
  "id": "prior_imaging_requirement",
  "title": "Prior Imaging Requirement",
  "description": "Weight-bearing X-rays must be completed within 60 days before PA request",
  "requirement_type": "all",
  "help_text": "Confirm X-rays were done recently and report is available",
  "items": [
    {
      "field": "xray_completed",
      "label": "X-rays of affected knee completed",
      "help_text": "Minimum 2 views required (AP and lateral); 3 views preferred. Weight-bearing AP view required unless contraindicated (document reason if omitted). Report must be available in medical record.",
      "input_type": "checkbox_with_detail",
      "detail_fields": [
        {
          "field": "xray_date",
          "label": "Date of X-rays",
          "input_type": "date",
          "validation": { "max_days_ago": 60 }
        },
        {
          "field": "weight_bearing_views",
          "label": "Weight-bearing views obtained?",
          "input_type": "text"
        },
        {
          "field": "contraindication_documented",
          "label": "If not weight-bearing, contraindication documented?",
          "input_type": "text"
        }
      ]
    }
  ]
}
```

**Impact:** Current structure is confusing for billing staff and doesn't properly capture the 60-day time requirement or contraindication scenario.

---

## ⚠️ MEDIUM PRIORITY ISSUES (Important Improvements)

### Issue #4: Denial Prevention Tips - Too Generic

**Severity:** MEDIUM
**Location:** `denial_prevention_tips` array

**Problem:**
The tips are vague platitudes that don't reflect the **specific, concrete denial triggers** found in the policy language.

**Current (Generic):**
```json
"denial_prevention_tips": [
  "Ensure that the member's medical record includes a documented diagnosis that meets the criteria",
  "Verify that the member has completed the required conservative treatment",
  "Check that the prior authorization request includes all required documentation",
  "Confirm that the member's condition meets the criteria for an exception"
]
```

**Recommended (Specific & Actionable):**
```json
"denial_prevention_tips": [
  "ISOLATED anterior knee pain alone (patellofemoral syndrome) without mechanical symptoms → automatic denial. Must document locking, catching, or giving-way if present.",

  "Repeat MRI within 12 months → denied unless you document: (1) change in clinical status since prior MRI, (2) failed intervention since prior imaging, OR (3) pre-operative planning need.",

  "Conservative treatment documentation must include SPECIFIC DATES and DURATIONS. 'Patient tried PT' without session dates will be denied. PT notes must show at least 6 sessions with dates of service.",

  "McMurray's test or Lachman test documented as 'equivocal' or 'uncertain' does NOT meet the clinical findings requirement. Must be explicitly documented as POSITIVE.",

  "X-rays must be weight-bearing views unless contraindicated. If non-weight-bearing views were used, document the specific contraindication (e.g., unable to bear weight due to acute injury).",

  "NSAIDs trial must document: medication name, dose, frequency, and duration (minimum 4 weeks). If NSAIDs contraindicated, document reason and alternative analgesic used.",

  "For members 65+, surgical candidacy assessment is REQUIRED. If member is not a surgical candidate, must document how MRI will directly modify the non-surgical management plan.",

  "Workers' compensation injuries must be billed to the WC carrier, NOT Utah Medicaid. Medicaid will deny.",

  "Member declines surgery → MRI denied UNLESS you document that results will directly change non-surgical treatment approach (e.g., modify PT protocol, adjust bracing)."
]
```

**Impact:** Generic tips don't help billing staff prevent actual denials. Specific tips based on policy language will reduce denial rates.

---

### Issue #5: Submission Reminders - Missing Key Details

**Severity:** MEDIUM
**Location:** `submission_reminders` array

**Problem:**
Current reminders are vague and miss critical procedural information from the policy.

**Current:**
```json
"submission_reminders": [
  "Submit the prior authorization request with all required documentation",
  "Ensure that the X-ray report is dated within 60 days of the PA request",
  "Verify that the member's medical record includes documentation of the intended treatment plan",
  "Check the Utah Medicaid website for updates"
]
```

**Recommended:**
```json
"submission_reminders": [
  "Authorization valid for 60 calendar days from approval date. If imaging not completed within 60 days, must submit new PA.",

  "Processing times: Standard 3-5 business days, Expedited 72 hours (requires clinical justification), Emergency same-day by phone.",

  "Submission methods: Electronic via medicaid.utah.gov/pa-portal (preferred), Fax 1-801-555-0100, Phone 1-800-662-9651 (M-F 8am-5pm MT).",

  "REQUIRED documentation checklist: (1) Clinical notes from within 30 days including exam findings, (2) Conservative treatment records with dates and outcomes, (3) X-ray report dated within 60 days, (4) ICD-10 code(s), (5) Statement of medical necessity and treatment plan impact.",

  "For exceptions: Include specific documentation (e.g., for acute trauma: ED report showing inability to bear weight; for post-op: surgical date and operative report reference).",

  "Incomplete submissions cause delays or denials. Review Section 5 of policy before submitting.",

  "Denials may be appealed per Utah Medicaid Fair Hearing procedures (Utah Admin. Code R414-301)."
]
```

**Impact:** Missing procedural details causes confusion and delays in PA submissions.

---

### Issue #6: Help Text Lacks Specificity

**Severity:** MEDIUM
**Location:** Various item `help_text` fields

**Problem:**
Many help_text fields are too brief and don't include the concrete documentation requirements that would prevent denials.

**Examples:**

#### Example 1: Positive McMurray's Test
**Current:**
```json
{
  "field": "positive_mcmurrays_test",
  "label": "Positive McMurray's Test",
  "help_text": "Documented positive McMurray's test"
}
```

**Improved:**
```json
{
  "field": "positive_mcmurrays_test",
  "label": "Positive McMurray's Test",
  "help_text": "Must be explicitly documented as 'positive' (not 'equivocal' or 'deferred'). Must be documented within 30 days of PA request date. Exam note must include examiner name and date."
}
```

#### Example 2: Physical Therapy
**Current:**
```json
{
  "field": "physical_therapy",
  "label": "Physical Therapy",
  "help_text": "Minimum of 6 documented sessions with a licensed physical therapist"
}
```

**Improved:**
```json
{
  "field": "physical_therapy",
  "label": "Physical Therapy (≥6 sessions over ≥6 weeks)",
  "help_text": "Minimum 6 PT sessions with licensed physical therapist over at least 6 weeks total. PT notes must include: dates of service for each session, treatment techniques used, and functional status assessments. 'Patient saw PT' without specific dates and session count will be denied."
}
```

#### Example 3: Joint Line Tenderness
**Current:**
```json
{
  "field": "joint_line_tenderness",
  "label": "Joint Line Tenderness",
  "help_text": "Documented joint line tenderness with mechanical symptoms"
}
```

**Improved:**
```json
{
  "field": "joint_line_tenderness",
  "label": "Joint line tenderness + mechanical symptoms",
  "help_text": "Document location (medial/lateral joint line) AND associated mechanical symptoms (locking, catching, or giving-way). Tenderness alone without mechanical symptoms does NOT meet this criterion."
}
```

**Recommendation:** Review all help_text fields and enhance with:
- Specific documentation requirements (dates, names, durations)
- Common mistakes that lead to denials
- What constitutes insufficient documentation

---

## ✅ WHAT WORKED WELL (No Changes Needed)

### Strengths:
1. **Overall Structure** - 4 main sections correctly identified
2. **Requirement Types** - Mostly correct use of "any", "all", "count_gte" (except conservative treatment)
3. **Eligible Diagnosis Section** - All ICD-10 codes captured accurately, proper categorization
4. **Clinical Findings Section** - All 6 findings captured, correct requirement_type
5. **Exception Pathways** - Excellent capture of all 3 exception types with correct waives references
6. **Exclusions** - Perfect capture of all 6 exclusion scenarios
7. **ICD-10 Codes** - Accurate throughout
8. **Input Types** - Good use of checkbox, date, text, and checkbox_with_detail

---

## 📋 CURATION CHECKLIST

Before deploying this checklist to production, complete the following:

- [ ] **CRITICAL:** Fix conservative treatment to `count_gte` with `threshold: 2`
- [ ] **HIGH:** Add special populations section (under 18, 65+)
- [ ] **MEDIUM:** Restructure prior imaging section (consolidate to one item with detail_fields)
- [ ] **MEDIUM:** Rewrite denial prevention tips with specific, actionable advice
- [ ] **MEDIUM:** Enhance submission reminders with procedural details
- [ ] **MEDIUM:** Review and enhance all help_text fields for specificity
- [ ] Verify all ICD-10 codes against current CMS ICD-10-CM database
- [ ] Test checklist with 2-3 sample PA scenarios to ensure clarity
- [ ] Review policy effective date (currently set to 2025-01-01) - confirm this is accurate
- [ ] Add `last_curated` field with today's date after completing review
- [ ] Add `curator_notes` field documenting changes made from LLM draft

---

## 🎯 RECOMMENDED WORKFLOW

1. **Copy the compiled JSON** to a new file: `utah_medicaid_73721_CURATED.rules.json`
2. **Make the CRITICAL fix** (conservative treatment requirement_type)
3. **Add special populations section**
4. **Enhance denial tips and submission reminders** using recommended text above
5. **Review and enhance all help_text fields** one by one
6. **Add curation metadata:**
   ```json
   {
     "last_curated": "2026-02-23",
     "curator_notes": "Fixed conservative treatment requirement_type (was 'all', corrected to 'count_gte' threshold 2). Added special populations section. Enhanced denial tips and help_text throughout."
   }
   ```
7. **Test the checklist** by walking through 2-3 real or simulated PA scenarios
8. **Deploy to production** rules directory

---

## 📊 VALIDATION RESULTS

**Validation Errors:** 0 (structure is valid)
**Logical Errors:** 1 (conservative treatment requirement_type)
**Completeness:** 85% (missing special populations)
**Clarity:** 70% (help_text needs enhancement)

**Overall Assessment:** Good first draft, needs human curation before production use.

---

## NEXT STEPS

1. Use this review to manually curate the checklist
2. Save curated version to `rules/utah_medicaid_73721.rules.json`
3. Update `rules/metadata/payer_cpt_index.json` to include this checklist
4. Test PDF generation with curated checklist
5. Consider compiling additional Utah Medicaid CPT codes (73722, 73723) for completeness
