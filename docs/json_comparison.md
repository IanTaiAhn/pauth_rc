# Prior Authorization Rules Engine

A flexible, extensible rules engine for evaluating patient eligibility for prior authorization based on policy criteria.

## Key Improvements

### 1. **Flexible Field Access**
- Uses dot notation for nested fields: `"conservative_therapy.physical_therapy.weeks"`
- Handles multiple JSON structures automatically
- No hardcoded assumptions about data structure

### 2. **Rich Comparison Operators**
- `gte`, `gt`, `lte`, `lt` - Numeric comparisons
- `eq`, `neq` - Equality checks
- `in` - Check if value is in a list
- `contains` - Check if list contains value
- `any_in` - Check for any overlap between lists

### 3. **Detailed Results**
- Shows which conditions passed/failed
- Displays actual patient values vs. required values
- Provides comprehensive feedback for denials

### 4. **Multiple Logic Types**
- `all` - All conditions must pass (AND logic)
- `any` - At least one condition must pass (OR logic)
- Can be specified per rule

## Architecture

```
Patient Chart JSON → normalize_patient_evidence() → Flat Dictionary
                                                           ↓
Policy Criteria JSON → normalize_policy_criteria() → Rule List
                                                           ↓
                                              evaluate_all() → Results
```

## Usage

### Basic Example

```python
from rule_engine import evaluate_all
from normalize import normalize_patient_evidence, normalize_policy_criteria

# Your patient data (can be any structure)
patient_data = {
    "diagnosis": ["M54.5"],
    "symptom_duration_weeks": 8,
    "conservative_therapy": {
        "physical_therapy": {
            "completed_weeks": 6
        }
    }
}

# Your policy rules
policy = {
    "criteria": [
        {
            "id": "rule_1",
            "description": "Must have 6+ weeks of symptoms",
            "requirement": {
                "symptom_duration_weeks": {"min": 6}
            }
        }
    ]
}

# Normalize and evaluate
patient_norm = normalize_patient_evidence(patient_data)
policy_rules = normalize_policy_criteria(policy)
results = evaluate_all(patient_norm, policy_rules)

print(f"Approved: {results['all_criteria_met']}")
```

### FastAPI Integration

```python
from fastapi import FastAPI
from authz import router

app = FastAPI()
app.include_router(router, prefix="/api/prior-auth")

# POST /api/prior-auth/evaluate
# Request body:
# {
#   "patient_evidence": {"data": {...}},
#   "policy_criteria": {"data": {...}}
# }
```

## Customizing for Your JSON Structure

### 1. Adapt `normalize_patient_evidence()`

Look at your actual patient chart JSON and modify the normalization function:

```python
def normalize_patient_evidence(evidence: dict) -> dict:
    normalized = {}
    
    # Example: Your charts have "clinical_notes" → "symptoms" → "duration"
    if "clinical_notes" in evidence:
        notes = evidence["clinical_notes"]
        normalized["symptom_duration_weeks"] = notes.get("symptoms", {}).get("duration")
    
    # Example: Your diagnoses are in "conditions" array
    if "conditions" in evidence:
        normalized["diagnoses"] = [c["icd10"] for c in evidence["conditions"]]
    
    return normalized
```

### 2. Adapt `normalize_policy_criteria()`

Customize how policy requirements map to conditions:

```python
# Example: Your policies use "minimum_duration" instead of "min"
if "minimum_duration" in requirement:
    conditions.append({
        "field": "symptom_duration_weeks",
        "operator": "gte",
        "value": requirement["minimum_duration"]
    })
```

## Example JSON Formats

### Patient Chart Example 1 (Nested)
```json
{
  "diagnosis": ["M54.5", "M51.26"],
  "symptom_duration_weeks": 8,
  "conservative_therapy": {
    "physical_therapy": {
      "completed_weeks": 6,
      "sessions": 12
    },
    "nsaids": {
      "trialed": true,
      "outcome": "no relief"
    }
  },
  "imaging": {
    "mri": {
      "done": true,
      "months_ago": 2,
      "findings": "herniated disc L4-L5"
    }
  }
}
```

### Patient Chart Example 2 (Flat)
```json
{
  "diagnoses": ["M51.26"],
  "symptom_duration_weeks": 10,
  "pt_weeks": 8,
  "medications": ["ibuprofen"],
  "mri_done": true
}
```

### Policy Criteria Format
```json
{
  "criteria": [
    {
      "id": "symptom_duration",
      "description": "Patient must have symptoms for at least 6 weeks",
      "logic": "all",
      "requirement": {
        "symptom_duration_weeks": {"min": 6}
      }
    },
    {
      "id": "diagnosis",
      "description": "Patient must have qualifying diagnosis",
      "requirement": {
        "diagnosis_includes": ["M54.5", "M51.26", "M51.16"]
      }
    },
    {
      "id": "conservative_care",
      "description": "Complete 6 weeks PT OR try NSAIDs",
      "logic": "any",
      "requirement": {
        "physical_therapy_weeks": {"min": 6},
        "nsaid_trial_required": true
      }
    }
  ]
}
```

## Response Format

```json
{
  "results": [
    {
      "rule_id": "symptom_duration",
      "description": "Patient must have symptoms for at least 6 weeks",
      "met": true,
      "logic": "all",
      "condition_details": [
        {
          "condition": "symptom_duration_weeks gte 6",
          "patient_value": 8,
          "met": true
        }
      ]
    }
  ],
  "all_criteria_met": true,
  "total_rules": 4,
  "rules_met": 4,
  "rules_failed": 0
}
```

## Adding New Rule Types

### Custom Operators

Add to `compare_values()` in `rule_engine.py`:

```python
elif operator == "between":
    min_val, max_val = threshold
    return min_val <= patient_value <= max_val
```

### Complex Conditions

```python
# In policy criteria:
{
  "id": "imaging_recent",
  "description": "MRI done within 6 months",
  "requirement": {
    "mri_done": true,
    "mri_max_months_ago": 6
  }
}
```

## Error Handling

The system handles:
- Missing fields (returns `None`, evaluates to `False`)
- Type mismatches (caught in comparison functions)
- Unknown operators (raises `ValueError`)
- Invalid JSON structure (FastAPI validation)

## Testing

Run the test suite:

```bash
python test_rules.py
```

## Common Patterns

### "Must have X AND Y"
```json
{
  "logic": "all",
  "requirement": {
    "field_x": value_x,
    "field_y": value_y
  }
}
```

### "Must have X OR Y"
```json
{
  "logic": "any",
  "requirement": {
    "field_x": value_x,
    "field_y": value_y
  }
}
```

### "Must be between X and Y"
```json
{
  "requirement": {
    "age": {"min": 18, "max": 65}
  }
}
```

### "Must include any of these diagnoses"
```json
{
  "requirement": {
    "diagnosis_includes": ["M54.5", "M51.26"]
  }
}
```

## Next Steps

1. **Customize normalization** functions for your actual JSON formats
2. **Add validation** to ensure required fields are present
3. **Implement caching** for policy rules (they don't change often)
4. **Add logging** to track evaluation decisions
5. **Create a UI** to display detailed results to users
6. **Version policies** to track changes over time

## Support

For questions or issues, refer to the test cases in `test_rules.py` for working examples.