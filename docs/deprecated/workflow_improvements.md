# Workflow Improvements - Diagnostic Artifact Analysis

**Date**: 2026-02-16
**Analysis Source**: Comparison of 10 patient diagnostic artifacts (base vs .1/.2/exception versions)
**Files Analyzed**: `api_artifacts/diagnostic_artifact_patient_*.json`

---

## Executive Summary

Analysis of diagnostic artifacts revealed critical inconsistencies in the PA evaluation workflow that compromise the reliability of readiness scores and verdicts. The primary issues stem from inconsistent LLM data extraction, clinical indication mapping failures, and exception logic that doesn't align with scoring.

**Impact**: These issues can lead to incorrect PA readiness assessments, potentially causing:
- False denials (patients marked "LIKELY_TO_DENY" when they should be approved)
- Missed exclusions (Workers Compensation cases billed to Medicaid)
- Unnecessary imaging orders (repeat MRI requests when prior imaging exists)
- Inconsistent clinical decision support

---

## Issues Found by Category

### A. Data Extraction Inconsistencies

**Affected Patients**: 02 (Brittany Okafor), 03 (Marcus Webb), 08 (Robert Asante)

#### Issue 1: Null vs Actual Values
- **Problem**: `imaging_months_ago` and `clinical_indication` frequently null in base versions but populated in .1/.2 versions
- **Example**: Patient 02
  - Base version: `imaging_months_ago: null`, `clinical_indication: null` → FAIL (40% readiness)
  - .1 version: `imaging_months_ago: 0`, `clinical_indication: "red flag"` → PASS (75% readiness)
- **Impact**: 35% difference in readiness score for identical patient data
- **Root Cause**: LLM extraction not consistently calculating temporal values or mapping symptoms to indications

#### Issue 2: Evidence Notes Count Variations
- **Problem**: Different numbers of evidence notes extracted between versions
- **Examples**:
  - Patient 01: 5 notes vs 4 notes
  - Patient 03: 4 notes vs 3 notes
  - Patient 09: 6 notes vs 4 notes
- **Impact**: Inconsistent evidence presentation in reports; affects human review quality

---

### B. Clinical Indication Mapping Failures

**Affected Patients**: 01, 04, 06, 07, 09, 10

#### Issue 3: "Mechanical Symptoms" Not Mapped to Valid Policy Indications
- **Problem**: Patients with clear mechanical symptoms (locking, catching, giving-way) get `clinical_indication: "mechanical symptoms"` which is NOT in policy's accepted list
- **Policy Requires**: meniscal tear, positive mcmurray, red flag, post-operative
- **Example**: Patient 01 (Carlos Mendez)
  - Evidence notes: "mechanical 'catching' sensation", "intermittent locking of the knee"
  - Extracted indication: "mechanical symptoms" → FAIL
  - Should be: "meniscal tear" (mechanical symptoms are diagnostic for meniscal pathology)
- **Impact**: 4 out of 10 patients incorrectly failed clinical indication requirement

#### Issue 4: "Instability" Not Mapped
- **Problem**: Patient 07 has "instability" as clinical indication, not recognized by policy
- **Evidence**: "instability on uneven ground", "renewed effusion"
- **Impact**: Post-operative patient with valid symptoms marked as failing clinical criteria

---

### C. Policy Rule Variations

**Affected Patients**: 04 (Tyler Kaminsky)

#### Issue 5: Inconsistent PT Requirements Between Versions
- **Problem**: Different policy rules applied to same patient
- **Base version**: Requires `pt_duration_weeks >= 6` (minimum 6 weeks)
- **.2 version**: Only requires `pt_attempted == true` (no duration check)
- **Impact**:
  - Base: 80% readiness (4/5 criteria met, 1 failed)
  - .2: 75% readiness (4/5 criteria met, 1 failed)
  - Different scores despite same clinical data
- **Root Cause**: Policy extraction not consistent; rules should be deterministic

---

### D. Exception Logic Inconsistencies

**Affected Patients**: 03 (Marcus Webb), 05 (Randy Schaefer), 08 (Robert Asante)

#### Issue 6: Exception Verdicts Don't Align With Scores
- **Problem**: Lower readiness scores yielding better verdicts when exceptions applied
- **Example**: Patient 03
  - Base version: 40% readiness → "LIKELY_TO_DENY" (3 criteria failed)
  - Exception version: 25% readiness → "LIKELY_TO_APPROVE" (3 criteria failed + exception)
  - Exception applied: "Acute Trauma Exception - Section 3.1"
- **Issue**: Exception correctly bypasses rules, but score should reflect actual criteria met, not be lower
- **Impact**: Confusing to end users; 25% readiness + approval seems contradictory

#### Issue 7: Workers Compensation Detection Inconsistent
- **Problem**: WC exclusion only detected in one version
- **Example**: Patient 05 (Randy Schaefer)
  - Base version: "LIKELY_TO_DENY" (60% readiness)
  - Excluded version: "EXCLUDED" (0% readiness, WC case detected)
  - Evidence: "Right knee pain following workplace fall x 6 weeks", "modified duty, no kneeling"
- **Impact**: Without WC detection, clinic would submit PA to wrong payer (Medicaid instead of WC carrier)

#### Issue 8: Red Flag Exception Identification
- **Problem**: Red flags documented but not always triggering exception pathway
- **Example**: Patient 08 (Robert Asante)
  - Base: `red_flags: {documented: true}` but `clinical_indication: null` → DENY
  - Exception: `clinical_indication: "red flag"` → APPROVE with exception
  - Evidence: "fever to 102.4°F", "elevated WBC/CRP/ESR"
- **Impact**: Infection cases (medical emergencies) getting denied instead of expedited

---

### E. Repeat Imaging Detection Missing

**Affected Patients**: 07 (Jasmine Tran), 10 (Tiffany Osei)

#### Issue 9: Requesting MRI When Prior MRI Already Exists
- **Problem**: No check for existing imaging of the same modality
- **Example**: Patient 07
  - Requesting: CPT 73721 (MRI Knee Without Contrast)
  - Has: Prior MRI from 5 months ago (Grade 2 radial tear posterior horn medial meniscus)
  - Verdict: "LIKELY_TO_DENY" (60% readiness)
  - Should warn: "Review existing MRI before ordering new study"
- **Example**: Patient 10
  - Requesting: CPT 73721
  - Has: Prior MRI from 5 months ago showing known meniscal tear
  - Evidence notes: "worsening symptoms", "locking episodes", "failed non-surgical management"
- **Impact**:
  - Unnecessary healthcare costs (repeat $1,500+ exam)
  - Radiation exposure (if contrast used)
  - Missed opportunity to review existing studies for progression

---

### F. Verdict/Score Inconsistencies

**Affected Patients**: Multiple

#### Issue 10: Same Clinical Data, Different Scores
- **Patient 01**: 80% vs 75% (both "NEEDS_REVIEW", same gaps)
- **Patient 06**: 80% vs 75% (both "NEEDS_REVIEW", same gaps)
- **Patient 09**: 60% vs 50% (both "LIKELY_TO_DENY", same gaps)

**Root Cause**: Likely related to evidence note count variations affecting denominators in scoring calculation.

---

## Summary Priority Order

### 🔴 CRITICAL - Fix Immediately

#### 1. Fix Data Extraction Nulls
**Priority**: P0 - CRITICAL
**Impact**: Affects all evaluations; 35% score differences
**Affected**: Patients 02, 03, 08 (30% of test cases)

**Recommendation**: Add validation in `evidence.py`:
```python
def _validate_extraction_completeness(self, extracted_data: dict) -> tuple[bool, list[str]]:
    """Ensure critical fields are not null when source data suggests they should exist"""
    issues = []

    # If imaging is documented, months_ago should be calculable
    if extracted_data.get("imaging", {}).get("documented") == True:
        if extracted_data["imaging"].get("months_ago") is None:
            issues.append("Imaging documented but months_ago is null")

    # If red_flags documented, clinical_indication should be 'red flag'
    if extracted_data.get("red_flags", {}).get("documented") == True:
        if extracted_data.get("clinical_indication") is None:
            issues.append("Red flags documented but clinical_indication not set")

    return len(issues) == 0, issues
```

**Files to modify**:
- `backend/app/services/evidence.py`
- Add post-extraction validation step

---

#### 2. Fix Clinical Indication Mapping
**Priority**: P0 - CRITICAL
**Impact**: 40% of patients incorrectly failing clinical indication requirement
**Affected**: Patients 01, 04, 06, 07, 09, 10 (60% of test cases)

**Recommendation**: Add intelligent mapping in `normalization/normalized_custom.py`:
```python
def _map_clinical_indication(raw_patient: dict) -> str | None:
    """Map extracted symptoms to policy-recognized clinical indications"""

    # Check for red flags first (highest priority)
    if raw_patient.get("red_flags", {}).get("documented"):
        return "red flag"

    # Check evidence notes for specific conditions
    evidence = raw_patient.get("evidence_notes", [])
    evidence_text = " ".join(evidence).lower()

    # Direct mappings based on symptoms
    if "locking" in evidence_text or "giving-way" in evidence_text or "catching" in evidence_text:
        # Mechanical symptoms strongly suggest meniscal tear
        return "meniscal tear"

    if "mcmurray" in evidence_text or "positive mcmurray" in evidence_text:
        return "positive mcmurray"

    if "instability" in evidence_text and raw_patient.get("imaging", {}).get("findings"):
        findings = raw_patient["imaging"]["findings"].lower()
        if "post-operative" in findings or "surgery" in findings:
            return "post-operative"

    # Check imaging findings
    imaging = raw_patient.get("imaging", {})
    if imaging.get("findings"):
        findings = imaging["findings"].lower()
        if "meniscal tear" in findings or "meniscus" in findings:
            return "meniscal tear"

    # Fallback to raw clinical_indication
    return raw_patient.get("clinical_indication")
```

**Files to modify**:
- `backend/app/normalization/normalized_custom.py`
- Add `_map_clinical_indication()` function
- Call it in `normalize_patient_evidence()`

---

### 🟠 HIGH PRIORITY - Fix Within Sprint

#### 3. Add Repeat Imaging Detection
**Priority**: P1 - HIGH
**Impact**: Prevents unnecessary $1,500+ imaging orders
**Affected**: Patients 07, 10 (20% of test cases)

**Recommendation**: Add rule to `rule_engine.py`:
```python
class RepeatImagingRule:
    """Check if requesting imaging type already exists"""

    def __init__(self):
        self.id = "repeat_imaging_check"
        self.description = "Verify new imaging order when recent prior imaging exists"

    def evaluate(self, normalized_patient: dict, requested_cpt: str) -> dict:
        imaging_type = normalized_patient.get("imaging_type")
        imaging_months_ago = normalized_patient.get("imaging_months_ago")

        # Determine requested modality
        requested_modality = self._get_modality_from_cpt(requested_cpt)

        # If requesting same modality and recent study exists
        if imaging_type == requested_modality and imaging_months_ago is not None:
            if imaging_months_ago < 6:  # Less than 6 months old
                return {
                    "met": False,
                    "warning": f"Patient already has {imaging_type} from {imaging_months_ago} months ago.",
                    "recommendation": "REVIEW_EXISTING_IMAGING_FIRST",
                    "severity": "WARNING"
                }

        return {"met": True}

    def _get_modality_from_cpt(self, cpt: str) -> str:
        """Map CPT to imaging modality"""
        mri_cpts = ["73721", "73722", "73723"]
        ct_cpts = ["73700", "73701"]

        if cpt in mri_cpts:
            return "MRI"
        elif cpt in ct_cpts:
            return "CT"

        return "Unknown"
```

**Files to modify**:
- `backend/app/rules/rule_engine.py`
- Add `RepeatImagingRule` class
- Add warning system to evaluation output

---

#### 4. Standardize Exception Logic
**Priority**: P1 - HIGH
**Impact**: Verdict consistency; user trust in system
**Affected**: Patients 03, 08 (20% of test cases)

**Recommendation**: Update `readiness.py`:
```python
def compute_readiness_score_with_exceptions(
    evaluation_results: dict,
    exception_applied: str | None
) -> int:
    """
    Compute readiness score accounting for exceptions.

    Rules:
    - Base score = (rules_met / total_rules) * 100
    - If exception applied:
        - Red flag exceptions: base score (don't artificially inflate)
        - Acute trauma: base score (don't artificially inflate)
        - Workers comp exclusion: 0 (excluded)
    - Verdict determined by exception type, not just score
    """
    base_score = int((evaluation_results["rules_met"] / evaluation_results["total_rules"]) * 100)

    if not exception_applied:
        return base_score

    if "Workers' Compensation" in exception_applied or "Exclusion" in exception_applied:
        return 0  # Excluded cases

    # Don't inflate score for exceptions - they bypass rules but don't change readiness
    return base_score


def determine_verdict(
    readiness_score: int,
    exception_applied: str | None,
    rules_failed: int
) -> str:
    """
    Determine verdict with explicit exception handling.

    Priority order:
    1. Exclusions (WC) → EXCLUDED
    2. Red flag/trauma exceptions → LIKELY_TO_APPROVE (bypass normal rules)
    3. No exception:
        - 80%+ → LIKELY_TO_APPROVE
        - 60-79% → NEEDS_REVIEW
        - <60% → LIKELY_TO_DENY
    """
    if exception_applied:
        if "Workers' Compensation" in exception_applied or "Exclusion" in exception_applied:
            return "EXCLUDED"

        if "Red Flag" in exception_applied or "Acute Trauma" in exception_applied:
            # Exception pathway allows approval despite failed standard rules
            return "LIKELY_TO_APPROVE"

    # Standard scoring
    if readiness_score >= 80:
        return "LIKELY_TO_APPROVE"
    elif readiness_score >= 60:
        return "NEEDS_REVIEW"
    else:
        return "LIKELY_TO_DENY"
```

**Files to modify**:
- `backend/app/services/readiness.py`
- Separate score calculation from verdict determination
- Document exception hierarchy

---

#### 5. Add Workers Compensation Detection
**Priority**: P1 - HIGH
**Impact**: Prevent billing to wrong payer (legal/compliance issue)
**Affected**: Patient 05 (10% of test cases, but high severity)

**Recommendation**: Add to `normalized_custom.py`:
```python
def _detect_workers_compensation(raw_patient: dict) -> bool:
    """Detect if this is a workers compensation case"""
    evidence_notes = raw_patient.get("evidence_notes", [])
    evidence_text = " ".join(evidence_notes).lower()

    wc_keywords = [
        "workplace",
        "work-related",
        "workers comp",
        "workers' comp",
        "on the job",
        "job injury",
        "workplace injury",
        "workplace fall",
        "modified duty",
        "work injury",
        "injured at work"
    ]

    functional_impairment = raw_patient.get("functional_impairment", {}).get("description", "").lower()

    # Check evidence notes and functional impairment description
    all_text = evidence_text + " " + functional_impairment

    return any(keyword in all_text for keyword in wc_keywords)


def normalize_patient_evidence(raw_patient: dict, format_type: int = 1) -> dict:
    """Add WC detection to normalization"""
    normalized = {
        # ... existing normalization ...
    }

    # Add WC detection
    normalized["is_workers_compensation"] = _detect_workers_compensation(raw_patient)

    return normalized
```

**Files to modify**:
- `backend/app/normalization/normalized_custom.py`
- Add `_detect_workers_compensation()` function
- Add exclusion rule to `rule_engine.py`

---

### 🟡 MEDIUM PRIORITY - Fix Next Sprint

#### 6. Evidence Note Deduplication
**Priority**: P2 - MEDIUM
**Impact**: Report quality, consistency
**Affected**: Multiple patients

**Recommendation**: Add to `evidence.py`:
```python
def _deduplicate_evidence_notes(self, notes: list[str]) -> list[str]:
    """Remove duplicate or highly similar evidence notes"""
    unique_notes = []
    seen_normalized = set()

    for note in notes:
        # Normalize for comparison
        normalized = note.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace

        # Check if substantially similar note already exists
        if normalized not in seen_normalized:
            unique_notes.append(note)
            seen_normalized.add(normalized)

    return unique_notes[:10]  # Max 10 evidence notes for readability
```

**Files to modify**:
- `backend/app/services/evidence.py`
- Call deduplication in `extract_patient_evidence()`

---

#### 7. Policy Rule Versioning
**Priority**: P2 - MEDIUM
**Impact**: Audit trail, rule consistency
**Affected**: Patient 04

**Recommendation**: Add versioning to policy schema:
```python
class PolicyRuleSchema(BaseModel):
    """Enforce consistent policy rule structure"""
    id: str
    description: str
    logic: Literal["all", "any"]
    conditions: list[Condition]
    version: str = "1.0"  # Add versioning
    effective_date: str  # Track when rule became effective
    source_document: str  # Which policy document

# In extract_policy_rules.py
def _validate_policy_consistency(rules: list[dict]) -> bool:
    """Ensure PT requirement is consistently defined"""
    pt_rule = next((r for r in rules if r["id"] == "physical_therapy_requirement"), None)

    if pt_rule:
        conditions = pt_rule.get("conditions", [])

        # Ensure both attempted AND duration checks exist
        has_attempted_check = any(c.get("field") == "pt_attempted" for c in conditions)
        has_duration_check = any(c.get("field") == "pt_duration_weeks" for c in conditions)

        if not (has_attempted_check and has_duration_check):
            logger.warning(f"PT rule missing required conditions. Has attempted: {has_attempted_check}, Has duration: {has_duration_check}")
            return False

    return True
```

**Files to modify**:
- `backend/app/api_models/schemas.py`
- `backend/app/rag_pipeline/scripts/extract_policy_rules.py`
- Add validation check in policy extraction

---

#### 8. Add Workflow Validation Pipeline
**Priority**: P2 - MEDIUM
**Impact**: Quality assurance, regression prevention

**Recommendation**: Create new validation module:
```python
# New file: backend/app/validation/workflow_validator.py

class WorkflowValidator:
    """Validates complete PA evaluation workflow"""

    def validate_extraction_to_report(
        self,
        patient_chart_path: str,
        expected_cpt: str,
        payer: str
    ) -> dict:
        """Run full pipeline and validate each step"""

        validation_report = {
            "extraction": None,
            "normalization": None,
            "policy_retrieval": None,
            "rule_evaluation": None,
            "verdict_consistency": None,
            "overall_pass": False
        }

        try:
            # Step 1: Extract
            extracted = self._extract_patient_chart(patient_chart_path)
            validation_report["extraction"] = self._validate_extraction(extracted)

            # Step 2: Normalize
            normalized = normalize_patient_evidence(extracted)
            validation_report["normalization"] = self._validate_normalization(normalized)

            # Step 3: Get policy
            policy = self._get_policy_rules(payer, expected_cpt)
            validation_report["policy_retrieval"] = self._validate_policy(policy)

            # Step 4: Evaluate
            evaluation = evaluate_rules(normalized, policy)
            validation_report["rule_evaluation"] = self._validate_evaluation(evaluation)

            # Step 5: Check verdict consistency
            validation_report["verdict_consistency"] = self._validate_verdict_consistency(
                evaluation, normalized, policy
            )

            # Overall pass if all steps pass
            validation_report["overall_pass"] = all([
                validation_report["extraction"]["passed"],
                validation_report["normalization"]["passed"],
                validation_report["policy_retrieval"]["passed"],
                validation_report["rule_evaluation"]["passed"],
                validation_report["verdict_consistency"]["passed"]
            ])

        except Exception as e:
            validation_report["error"] = str(e)
            validation_report["overall_pass"] = False

        return validation_report

    def _validate_extraction(self, extracted: dict) -> dict:
        """Validate extraction completeness"""
        issues = []

        # Check for null critical fields
        if extracted.get("imaging", {}).get("documented") and not extracted["imaging"].get("months_ago"):
            issues.append("Imaging documented but months_ago is null")

        if extracted.get("red_flags", {}).get("documented") and not extracted.get("clinical_indication"):
            issues.append("Red flags documented but clinical_indication not set")

        # Check for PT duration if attempted
        pt = extracted.get("conservative_therapy", {}).get("physical_therapy", {})
        if pt.get("attempted") and not pt.get("duration_weeks"):
            issues.append("PT attempted but duration_weeks is null")

        return {
            "passed": len(issues) == 0,
            "issues": issues
        }

    def _validate_normalization(self, normalized: dict) -> dict:
        """Validate normalization output"""
        issues = []

        required_fields = [
            "pt_attempted", "imaging_documented", "clinical_indication",
            "validation_passed", "hallucinations_detected"
        ]

        for field in required_fields:
            if field not in normalized:
                issues.append(f"Missing required field: {field}")

        return {
            "passed": len(issues) == 0,
            "issues": issues
        }

    def _validate_verdict_consistency(self, evaluation: dict, normalized: dict, policy: dict) -> dict:
        """Validate verdict aligns with score and exceptions"""
        issues = []

        score = evaluation.get("readiness_score", 0)
        verdict = evaluation.get("verdict")
        exception = evaluation.get("exception_applied")

        # If exception is applied, verdict should reflect it
        if exception:
            if "Workers' Compensation" in exception and verdict != "EXCLUDED":
                issues.append(f"WC exception applied but verdict is {verdict}, should be EXCLUDED")

            if ("Red Flag" in exception or "Acute Trauma" in exception) and verdict != "LIKELY_TO_APPROVE":
                issues.append(f"Exception {exception} applied but verdict is {verdict}, should be LIKELY_TO_APPROVE")
        else:
            # No exception - check standard scoring
            if score >= 80 and verdict != "LIKELY_TO_APPROVE":
                issues.append(f"Score {score}% but verdict is {verdict}, should be LIKELY_TO_APPROVE")
            elif 60 <= score < 80 and verdict != "NEEDS_REVIEW":
                issues.append(f"Score {score}% but verdict is {verdict}, should be NEEDS_REVIEW")
            elif score < 60 and verdict != "LIKELY_TO_DENY":
                issues.append(f"Score {score}% but verdict is {verdict}, should be LIKELY_TO_DENY")

        return {
            "passed": len(issues) == 0,
            "issues": issues
        }
```

**Files to create**:
- `backend/app/validation/workflow_validator.py`
- `backend/app/validation/__init__.py`

---

#### 9. Automated Regression Testing
**Priority**: P2 - MEDIUM
**Impact**: Prevent future regressions

**Recommendation**: Create test suite with diagnostic artifacts:
```python
# backend/app/tests/test_diagnostic_artifacts.py

import pytest
from app.services.evidence import EvidenceExtractor
from app.normalization.normalized_custom import normalize_patient_evidence
from app.rules.rule_engine import evaluate_rules

class TestDiagnosticArtifacts:
    """Regression tests based on known issues from artifact analysis"""

    def test_patient_02_clinical_indication(self):
        """Ensure red flag detection works consistently"""
        # Patient 02 - Brittany Okafor
        chart_path = "backend/app/data/patient_info/patient_02_chart.txt"

        extractor = EvidenceExtractor()
        extracted = extractor.extract_patient_evidence(chart_path)
        normalized = normalize_patient_evidence(extracted)

        # Should detect red flag from effusion evidence
        assert normalized["clinical_indication"] == "red flag", \
            "Failed to detect red flag clinical indication"

        # Imaging months should be calculated, not null
        assert normalized["imaging_months_ago"] is not None, \
            "imaging_months_ago should not be null when imaging documented"

    def test_patient_03_exception_verdict(self):
        """Ensure exception logic produces consistent verdicts"""
        # Patient 03 - Marcus Webb (acute trauma)
        chart_path = "backend/app/data/patient_info/patient_03_chart.txt"

        # ... extract and evaluate ...

        # If acute trauma exception applies, verdict should be LIKELY_TO_APPROVE
        if evaluation.get("exception_applied") and "Acute Trauma" in evaluation["exception_applied"]:
            assert evaluation["verdict"] == "LIKELY_TO_APPROVE", \
                "Acute trauma exception should result in LIKELY_TO_APPROVE verdict"

    def test_patient_05_workers_comp_detection(self):
        """Ensure Workers Compensation cases are excluded"""
        # Patient 05 - Randy Schaefer (WC case)
        chart_path = "backend/app/data/patient_info/patient_05_chart.txt"

        extractor = EvidenceExtractor()
        extracted = extractor.extract_patient_evidence(chart_path)
        normalized = normalize_patient_evidence(extracted)

        # Should detect WC case
        assert normalized.get("is_workers_compensation") == True, \
            "Failed to detect workers compensation case"

        # Verdict should be EXCLUDED
        # ... evaluate rules ...
        assert evaluation["verdict"] == "EXCLUDED", \
            "Workers compensation cases should be EXCLUDED"

    def test_patient_07_repeat_imaging_warning(self):
        """Ensure repeat imaging detection works"""
        # Patient 07 - Jasmine Tran (has prior MRI)
        chart_path = "backend/app/data/patient_info/patient_07_chart.txt"

        # ... extract and evaluate ...

        # Should warn about existing MRI
        assert normalized["imaging_type"] == "MRI", \
            "Should detect existing MRI imaging"

        # Should have warning about repeat imaging
        warnings = evaluation.get("warnings", [])
        assert any("already has MRI" in w.lower() for w in warnings), \
            "Should warn about existing MRI when requesting new MRI"

    def test_patient_01_mechanical_symptoms_mapping(self):
        """Ensure mechanical symptoms map to meniscal tear"""
        # Patient 01 - Carlos Mendez (mechanical symptoms)
        chart_path = "backend/app/data/patient_info/patient_01_chart.txt"

        extractor = EvidenceExtractor()
        extracted = extractor.extract_patient_evidence(chart_path)
        normalized = normalize_patient_evidence(extracted)

        # Evidence: "mechanical 'catching' sensation", "intermittent locking"
        # Should map to "meniscal tear" not "mechanical symptoms"
        assert normalized["clinical_indication"] in ["meniscal tear", "positive mcmurray"], \
            f"Mechanical symptoms should map to valid indication, got: {normalized['clinical_indication']}"
```

**Files to create**:
- `backend/app/tests/test_diagnostic_artifacts.py`
- Add patient chart test data to `backend/app/data/patient_info/`

---

### 📋 Documentation Updates

#### 10. Update CLAUDE.md
**Priority**: P2 - MEDIUM

**Recommendation**: Add Quality Assurance section:
```markdown
## Quality Assurance Checklist

Before deploying any PA evaluation pipeline changes, verify:

### Data Extraction Quality
- [ ] All documented clinical fields populated (no unexpected nulls)
- [ ] Temporal calculations working (imaging_months_ago, symptom_duration_months)
- [ ] Red flags triggering clinical indication = "red flag"
- [ ] Evidence notes deduplicated (max 10 unique notes)

### Clinical Indication Mapping
- [ ] Mechanical symptoms (locking, catching, giving-way) → "meniscal tear"
- [ ] Documented red flags → "red flag"
- [ ] Instability post-op → "post-operative"
- [ ] McMurray test documented → "positive mcmurray"

### Rule Engine Validation
- [ ] Policy rules consistent (PT requires attempted AND duration >= 6 weeks)
- [ ] Repeat imaging detection working
- [ ] Workers compensation exclusion working
- [ ] Exception logic produces correct verdicts

### Verdict Consistency
- [ ] No exception + 80%+ score → LIKELY_TO_APPROVE
- [ ] No exception + 60-79% score → NEEDS_REVIEW
- [ ] No exception + <60% score → LIKELY_TO_DENY
- [ ] Red flag/trauma exception → LIKELY_TO_APPROVE
- [ ] Workers comp → EXCLUDED

### Regression Testing
- [ ] All diagnostic artifact tests passing
- [ ] No score variations >5% for same clinical data
- [ ] Evidence note count consistent between runs
```

**Files to modify**:
- `CLAUDE.md`
- Add QA checklist section
- Document known edge cases from artifact analysis

---

## Implementation Roadmap

### Week 1: Critical Fixes
- [ ] Priority 1: Fix data extraction nulls (`evidence.py`)
- [ ] Priority 2: Fix clinical indication mapping (`normalized_custom.py`)
- [ ] Test on all 10 diagnostic artifacts
- [ ] Verify score improvements

### Week 2: High Priority Features
- [ ] Priority 3: Add repeat imaging detection (`rule_engine.py`)
- [ ] Priority 4: Standardize exception logic (`readiness.py`)
- [ ] Priority 5: Add Workers Comp detection (`normalized_custom.py`)
- [ ] Integration testing

### Week 3: Quality Assurance
- [ ] Priority 6-7: Evidence deduplication, policy versioning
- [ ] Priority 8: Build workflow validator
- [ ] Priority 9: Create regression test suite
- [ ] Priority 10: Update documentation

### Week 4: Validation & Deployment
- [ ] Run all regression tests
- [ ] Validate against diagnostic artifacts (all should improve)
- [ ] Update CLAUDE.md with QA checklist
- [ ] Deploy to staging environment

---

## Success Metrics

After implementing these fixes, we should see:

1. **Data Extraction**: 0% null values for `imaging_months_ago` when imaging documented
2. **Clinical Indication**: 100% of mechanical symptom cases mapped to "meniscal tear"
3. **Score Consistency**: <5% variation in readiness scores for identical patient data
4. **Exception Logic**: 100% of red flag/trauma exceptions → LIKELY_TO_APPROVE verdict
5. **WC Detection**: 100% of workplace injury cases → EXCLUDED verdict
6. **Repeat Imaging**: 100% of same-modality requests within 6 months flagged with warning

---

## Related Files

- **This Document**: `docs/workflow_improvements.md`
- **Diagnostic Artifacts**: `api_artifacts/diagnostic_artifact_patient_*.json`
- **Main Workflow**: Described in `CLAUDE.md`
- **Architecture**: `docs/mvp.md`
- **Normalization Details**: `backend/app/normalization/README.md`

---

## Conclusion

These issues represent systematic workflow problems that compound across the pipeline. Fixing them in priority order will:

1. Immediately improve clinical accuracy (P0 fixes)
2. Prevent billing errors and unnecessary procedures (P1 fixes)
3. Establish quality assurance processes (P2 fixes)

The root cause is **inconsistent LLM extraction** and **inadequate post-processing validation**. The solution is **deterministic validation layers** at each pipeline stage:

```
Chart → LLM Extract → VALIDATE → Normalize → VALIDATE → Rules → VALIDATE → Report
```

This aligns with CLAUDE.md's core principle: **"This is clinical decision support, not clinical decision automation."** We must ensure the decision support is reliable before clinicians can trust it.
