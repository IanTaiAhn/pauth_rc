# Policy Outline: Utah Medicaid CPT 73721 (MRI Knee Without Contrast)

> **Purpose:** This outline maps each policy section to its evaluable requirements.
> Review this against the source policy (DMHF-IMG-MRI-001, effective 2025-01-01)
> and correct any errors before using it to generate the field registry and rules.
>
> **Review instructions:** For each section below, open the policy document to the
> cited section number and confirm: (1) the logic is correct, (2) all conditions
> are listed, (3) nothing is missing, (4) thresholds are right.

---

## Policy Metadata

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| Payer              | Utah Medicaid                              |
| CPT Code           | 73721                                      |
| Description        | MRI knee, without contrast                 |
| Policy Reference   | DMHF-IMG-MRI-001                           |
| Effective Date     | 2025-01-01                                 |
| Auth Validity      | 60 calendar days from approval             |
| Domain             | knee_mri                                   |

---

## Section 2: Coverage Criteria

**Top-level logic:** ALL of sections 2.1–2.4 must be met (plus 2.5 if applicable).

### Section 2.1 — Eligible Diagnosis
- **Logic:** ANY one diagnosis required
- **Fields needed:** `icd10_code` (string, matched against allowed list)
- **Allowed values:**
  - Category A (structural pathology): M23.20x, M23.21x, M23.22x, M23.30x, S83.5xx, S83.6xx, S83.9xx, M23.60x, M23.61x, M23.62x, M93.2xx, M25.561, M25.562, M25.569
  - Category B (OA surgical planning): M17.0x, M17.1x, M17.2x, M17.3x
- **Note:** Category B requires surgical candidacy per Section 2.5

### Section 2.2 — Clinical Findings
- **Logic:** ANY one finding required
- **Timing constraint:** Within 30 days prior to PA request
- **Fields needed (all boolean):**
  - `mcmurray_test` — Positive McMurray's test
  - `thessaly_test` — Positive Thessaly test
  - `joint_line_tenderness` — Joint line tenderness WITH mechanical symptoms (locking, catching, giving way)
  - `persistent_effusion` — Persistent joint effusion > 4 weeks
  - `lachman_test` — Positive Lachman test
  - `anterior_posterior_drawer` — Positive anterior/posterior drawer test
  - `varus_valgus_instability` — Instability on varus or valgus stress testing
  - `restricted_rom_mechanical_block` — Restricted ROM with documented mechanical block

### Section 2.3 — Prior Imaging
- **Logic:** ALL conditions required
- **Timing constraint:** Within 60 calendar days prior to PA request
- **Fields needed:**
  - `xray_completed` (boolean) — Weight-bearing radiographs completed
  - `xray_report_available` (boolean) — Radiograph report in medical record

### Section 2.4 — Conservative Treatment
- **Logic:** COUNT_GTE — at least **2 of 5** modalities completed
- **Duration constraint:** Minimum 6 weeks (42 consecutive calendar days) total
- **Fields needed (all boolean):**
  - `pt_completed` — Physical therapy (≥6 sessions with licensed PT)
  - `nsaid_trial` — NSAIDs or oral analgesics (≥4 weeks documented trial)
  - `activity_modification` — Activity modification + documented home exercise program
  - `bracing_orthotics` — Bracing, orthotics, or assistive devices
  - `injection` — Intra-articular injection (corticosteroid or hyaluronic acid)
- **Note:** NSAIDs contraindication with documented alternative satisfies medication trial

### Section 2.5 — Special Population Requirements

#### Section 2.5(a) — Members Under 18
- **Logic:** ALL conditions required (only evaluated if patient age < 18)
- **Fields needed:**
  - `pediatric_ortho_eval` (boolean) — Evaluation by board-certified/eligible pediatric orthopedic surgeon
  - `growth_plate_assessment` (boolean) — Physeal assessment included

#### Section 2.5(b) — Members Age 65+
- **Logic:** ALL conditions required (only evaluated if patient age ≥ 65)
- **Fields needed:**
  - `functional_impact_adl` (boolean) — Functional impact on ADLs documented
  - `surgical_candidacy_assessed` (boolean) — Surgical candidacy assessment documented
- **Note:** If not a surgical candidate, MRI covered only if results will change non-surgical management

---

## Section 3: Exceptions to Conservative Treatment

**Effect:** If ANY exception is met, Section 2.4 (conservative treatment) is WAIVED.
**All other requirements (2.1, 2.2, 2.3, 2.5) still apply.**

### Section 3.1 — Acute Traumatic Injury
- **Logic:** ANY one condition triggers exception
- **Fields needed (all boolean):**
  - `acute_trauma` — Acute traumatic injury present
  - `inability_bear_weight` — Cannot bear weight at time of evaluation
  - `suspected_ligament_rupture` — Suspected complete rupture of ACL/PCL/MCL/LCL
  - `displaced_meniscal_tear` — Clinical findings consistent with displaced meniscal tear (locked knee)
- **Overrides:** conservative_treatment

### Section 3.2 — Post-Operative
- **Logic:** ALL conditions required
- **Fields needed:**
  - `post_op_evaluation` (boolean) — Post-op evaluation required
  - `surgical_date` (string, date) — Surgical date documented
- **Timing constraint:** Within 6 months of knee surgery
- **Overrides:** conservative_treatment

### Section 3.3 — Red Flag
- **Logic:** ANY one condition triggers exception
- **Fields needed (all boolean):**
  - `suspected_infection` — Suspected joint infection / septic arthritis
  - `suspected_tumor` — Suspected primary or metastatic tumor
  - `suspected_occult_fracture` — Suspected occult fracture not seen on X-ray
- **Overrides:** conservative_treatment

---

## Section 4: Exclusions

**Effect:** If ANY exclusion is fully met, PA is DENIED regardless of other criteria.

### 4(a) — No Clinical Indication
- **Logic:** ALL (single condition)
- **Field:** `no_clinical_indication` (boolean) — No symptoms, routine screening

### 4(b) — Isolated Anterior Knee Pain
- **Logic:** ALL of these must be true simultaneously
- **Fields:**
  - `isolated_anterior_knee_pain` (boolean) — Patellofemoral syndrome
  - `mechanical_symptoms_absent` (boolean) — No locking, catching, giving way
  - `instability_absent` (boolean) — No instability
- **Note:** If mechanical symptoms OR instability ARE present, this exclusion does NOT apply

### 4(c) — Mild OA Without Surgical Planning
- **Logic:** ALL
- **Fields:**
  - `mild_osteoarthritis` (boolean) — Mild OA diagnosed
  - `surgical_planning_absent` (boolean) — No surgical planning intended

### 4(d) — Workers Compensation
- **Logic:** ALL (single condition)
- **Field:** `workers_comp` (boolean) — WC injury

### 4(e) — Member Declines Surgery
- **Logic:** ALL (single condition)
- **Field:** `declines_surgery` (boolean) — Declines surgical intervention
- **Note:** Exception if MRI will directly modify non-surgical management (must be documented)

### 4(f) — Repeat MRI Within 12 Months
- **Logic:** ALL of these must be true simultaneously for exclusion to apply
- **Fields:**
  - `repeat_mri_within_12mo` (boolean) — Is this a repeat MRI within 12 months
  - `no_clinical_status_change` (boolean) — No documented change in clinical status
  - `no_failed_intervention` (boolean) — No failed intervention since prior imaging
  - `no_preop_planning` (boolean) — No pre-operative planning requirement

---

## Field Inventory Summary

| Category            | Count | Fields |
|---------------------|-------|--------|
| Diagnosis           | 1     | icd10_code |
| Clinical findings   | 8     | mcmurray_test, thessaly_test, joint_line_tenderness, persistent_effusion, lachman_test, anterior_posterior_drawer, varus_valgus_instability, restricted_rom_mechanical_block |
| Prior imaging       | 2     | xray_completed, xray_report_available |
| Conservative tx     | 5     | pt_completed, nsaid_trial, activity_modification, bracing_orthotics, injection |
| Special populations | 4     | pediatric_ortho_eval, growth_plate_assessment, functional_impact_adl, surgical_candidacy_assessed |
| Exception fields    | 8     | acute_trauma, inability_bear_weight, suspected_ligament_rupture, displaced_meniscal_tear, post_op_evaluation, surgical_date, suspected_infection, suspected_tumor, suspected_occult_fracture |
| Exclusion fields    | 9     | no_clinical_indication, isolated_anterior_knee_pain, mechanical_symptoms_absent, instability_absent, mild_osteoarthritis, surgical_planning_absent, workers_comp, declines_surgery, repeat_mri_within_12mo, no_clinical_status_change, no_failed_intervention, no_preop_planning |
| **Total**           | **37+** | |

---

## Review Checklist

- [ ] Section 2.1: All ICD-10 codes match policy document
- [ ] Section 2.2: All 6 clinical finding categories covered (a–f)
- [ ] Section 2.3: Timing constraint (60 days) noted
- [ ] Section 2.4: Logic is count_gte with threshold 2 (not "any" or "all")
- [ ] Section 2.4: Duration constraint (6 weeks) noted
- [ ] Section 2.5: Age-conditional logic noted for under-18 and over-65
- [ ] Section 3: All three exception pathways override ONLY conservative treatment
- [ ] Section 3.2: Post-op requires ALL (both fields), not ANY
- [ ] Section 4: Each exclusion is a separate rule (not collapsed into one)
- [ ] Section 4(b): Three-condition exclusion (pain + no mechanical + no instability)
- [ ] Section 4(f): Four-condition exclusion (repeat + no change + no failed + no preop)
- [ ] Field names are consistent, readable, and unambiguous
- [ ] No duplicate fields under different names
