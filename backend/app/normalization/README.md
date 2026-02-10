# JSON Normalization Module

This module provides functions to normalize patient chart JSON (extracted from medical records) and insurance policy JSON (from RAG-powered document retrieval) into standardized formats for comparison and validation.

## Overview

The normalization process converts two different JSON structures into a common format that the rule engine can evaluate:

1. **Patient Evidence JSON** → Flat dictionary with standardized field names
2. **Insurance Policy JSON** → List of rules with standardized condition format

## Files

- `normalized_custom.py` - **Production normalizers** (currently used in `authz.py`)
- `normalize_NU.py` - Generic normalizer with comprehensive field handling
- `normalize_patient_evidence_NU.py` - Simplified patient normalizer
- `normalize_policy_criteria_NU.py` - Simplified policy normalizer

## Patient Evidence Normalization

### Input Format

```json
{
  "timestamp": "2026-01-27T16:32:19.659972",
  "analysis": {
    "filename": "patient_chart.txt",
    "score": 100,
    "requirements": {
      "symptom_duration_months": 4,
      "conservative_therapy": {
        "physical_therapy": {
          "attempted": true,
          "duration_weeks": 12
        },
        "nsaids": {
          "documented": true,
          "outcome": "failed"
        }
      },
      "imaging": {
        "documented": true,
        "type": "X-ray",
        "months_ago": 1
      },
      "_metadata": {
        "validation_passed": true,
        "hallucinations_detected": 0
      }
    }
  }
}
```

### Output Format

```python
{
    "symptom_duration_months": 4,
    "symptom_duration_weeks": 16,
    "pt_attempted": True,
    "pt_duration_weeks": 12,
    "nsaid_documented": True,
    "nsaid_outcome": "failed",
    "nsaid_failed": True,
    "imaging_documented": True,
    "imaging_type": "X-ray",
    "imaging_months_ago": 1,
    "validation_passed": True,
    "hallucinations_detected": 0,
    # ... additional fields
}
```

### Key Features

- **Flexible field mapping**: Handles multiple possible field names (e.g., `duration_weeks`, `weeks`, `duration`)
- **Type normalization**: Standardizes values like "X-ray", "x-ray", "XRAY" → "X-ray"
- **Unit conversion**: Automatically converts months ↔ weeks, days → months
- **Outcome detection**: Intelligently detects failed outcomes ("failed", "no relief", "unsuccessful")
- **Safe defaults**: Provides sensible defaults for missing fields

## Insurance Policy Normalization

### Input Format

```json
{
  "rules": {
    "payer": "Aetna",
    "cpt_code": "73721",
    "coverage_criteria": {
      "clinical_indications": [...],
      "prerequisites": [
        "Weight-bearing X-rays must be completed within 60 days"
      ],
      "documentation_requirements": [
        "Physical therapy notes with dates and sessions",
        "Medication trial documentation"
      ]
    }
  },
  "context": [
    "Member must have completed at least 6 WEEKS of conservative therapy...",
    "NSAIDs trial of at least 4 weeks..."
  ]
}
```

### Output Format

```python
[
    {
        "id": "imaging_requirement",
        "description": "Imaging (X-ray) must be completed within 2 months",
        "logic": "all",
        "conditions": [
            {"field": "imaging_documented", "operator": "eq", "value": True},
            {"field": "imaging_months_ago", "operator": "lte", "value": 2}
        ]
    },
    {
        "id": "physical_therapy_requirement",
        "description": "Physical therapy must be attempted (minimum 6 weeks)",
        "logic": "all",
        "conditions": [
            {"field": "pt_attempted", "operator": "eq", "value": True},
            {"field": "pt_duration_weeks", "operator": "gte", "value": 6}
        ]
    },
    # ... additional rules
]
```

### Key Features

- **Context-aware parsing**: Extracts requirements from both structured fields and context text
- **Intelligent extraction**: Finds timeframes (60 days, 6 weeks), durations, and thresholds
- **Flexible matching**: Handles variations in phrasing and formatting
- **Comprehensive rules**: Generates rules for imaging, therapy, medications, documentation quality
- **Regex pattern matching**: Uses regex to extract numeric requirements from text

## Usage

### Basic Usage

```python
from backend.app.normalization.normalized_custom import (
    normalize_patient_evidence,
    normalize_policy_criteria
)
from backend.app.rules.rule_engine import evaluate_all

# Load your JSON data
patient_json = {...}  # Patient chart JSON
policy_json = {...}   # Insurance policy JSON

# Normalize both
patient_norm = normalize_patient_evidence(patient_json)
policy_rules = normalize_policy_criteria(policy_json)

# Evaluate
results = evaluate_all(patient_norm, policy_rules)

# Check results
if results["all_criteria_met"]:
    print("✅ Prior Authorization APPROVED")
else:
    print(f"❌ Prior Authorization DENIED")
    print(f"Rules failed: {results['rules_failed']}/{results['total_rules']}")
```

### Manual Rule Specification

```python
from backend.app.normalization.normalized_custom import normalize_policy_criteria_manual

# Define custom rules
custom_rules = [
    {
        "id": "pt_duration",
        "description": "PT must be at least 6 weeks",
        "logic": "all",
        "conditions": [
            {"field": "pt_duration_weeks", "operator": "gte", "value": 6}
        ]
    }
]

# Use manual rules
policy_rules = normalize_policy_criteria_manual(policy_json, custom_rules=custom_rules)
```

### Validation

```python
from backend.app.normalization.normalized_custom import (
    validate_normalized_patient,
    validate_normalized_rules
)

# Validate patient data
is_valid, missing_fields = validate_normalized_patient(patient_norm)
if not is_valid:
    print(f"Missing required fields: {missing_fields}")

# Validate policy rules
is_valid, errors = validate_normalized_rules(policy_rules)
if not is_valid:
    print(f"Rule validation errors: {errors}")
```

### Summary Generation

```python
from backend.app.normalization.normalized_custom import get_normalization_summary

# Get human-readable summary
summary = get_normalization_summary(patient_norm)
print(summary)
```

## Supported Operators

The rule engine supports these comparison operators:

- `eq` - Equal to
- `neq` - Not equal to
- `gt` - Greater than
- `gte` - Greater than or equal to
- `lt` - Less than
- `lte` - Less than or equal to
- `in` - Value in list
- `contains` - List contains value
- `any_in` - Any overlap between lists

## Extending the Normalizers

### Adding New Patient Fields

To add support for a new patient evidence field:

1. Update `normalize_patient_evidence()` to extract the field
2. Add appropriate default handling
3. Update `validate_normalized_patient()` if it's a required field

```python
# Example: Adding diagnosis field
diagnosis = requirements.get("diagnosis", {})
normalized["diagnosis_code"] = diagnosis.get("icd10_code")
normalized["diagnosis_description"] = diagnosis.get("description")
```

### Adding New Policy Rules

To add a new rule extraction pattern:

1. Check for relevant keywords in prerequisites/documentation
2. Parse requirements from context using regex if needed
3. Build condition objects with appropriate operators

```python
# Example: Adding injection requirement
if "injection" in doc_text.lower():
    rules_list.append({
        "id": "injection_requirement",
        "description": "Injection trial must be documented",
        "logic": "all",
        "conditions": [
            {"field": "injection_documented", "operator": "eq", "value": True}
        ]
    })
```

## Testing

Run the test suite:

```bash
cd /path/to/backend
python app/tests/tests_custom.py
```

This will run three test scenarios:
1. Automatic rule extraction from policy
2. Manual rule specification
3. Failing case (insufficient therapy)

## Best Practices

1. **Always normalize before comparison**: Never compare raw JSON directly
2. **Validate after normalization**: Use validation functions to catch issues early
3. **Handle missing data gracefully**: Use `.get()` with defaults
4. **Be flexible with field names**: Check multiple possible field names
5. **Use context intelligently**: Extract requirements from both structured data and text
6. **Test edge cases**: Ensure normalizers handle missing, null, and malformed data

## Common Issues

### Issue: Rule not extracting correctly
**Solution**: Check the `context` field in policy JSON - requirements may be in context text rather than structured fields

### Issue: Patient field is None
**Solution**: Add fallback field names or safe defaults in `normalize_patient_evidence()`

### Issue: Type mismatches in comparisons
**Solution**: Ensure consistent types (e.g., all durations as integers, all booleans as True/False)

## Future Improvements

- [ ] Add support for OR logic between rules (currently only AND)
- [ ] Implement fuzzy matching for text requirements
- [ ] Add caching for frequently used normalizations
- [ ] Support for multiple payers with different rule formats
- [ ] Automated extraction of numeric thresholds from natural language
