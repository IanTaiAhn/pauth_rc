# Migration Guide: Old → New Rules Engine

## Quick Start

**Before:**
```python
# Old code - hardcoded checks
def evaluate_rule(patient, rule):
    results = []
    checks = rule["checks"]
    
    if checks["min_symptom_duration_weeks"] is not None:
        results.append(patient["symptom_duration_weeks"] >= checks["min_symptom_duration_weeks"])
    
    return all(results)
```

**After:**
```python
# New code - flexible conditions
def evaluate_rule(patient_data: dict, rule: dict) -> dict:
    conditions = rule.get("conditions", [])
    results = [evaluate_condition(patient_data, cond) for cond in conditions]
    
    if rule.get("logic") == "any":
        met = any(results)
    else:
        met = all(results)
    
    return {"rule_id": rule["id"], "met": met, ...}
```

## Key Changes

### 1. Rule Structure

**Old Format:**
```json
{
  "id": "rule_1",
  "description": "...",
  "checks": {
    "min_symptom_duration_weeks": 6,
    "required_diagnoses": ["M54.5"],
    "min_pt_weeks": 6
  }
}
```

**New Format:**
```json
{
  "id": "rule_1",
  "description": "...",
  "logic": "all",
  "conditions": [
    {
      "field": "symptom_duration_weeks",
      "operator": "gte",
      "value": 6
    },
    {
      "field": "diagnoses",
      "operator": "any_in",
      "value": ["M54.5"]
    },
    {
      "field": "pt_completed_weeks",
      "operator": "gte",
      "value": 6
    }
  ]
}
```

### 2. Benefits of New Format

✅ **Extensible**: Add new operators without changing code
✅ **Flexible**: Support OR logic, ranges, complex conditions
✅ **Debuggable**: See exactly which conditions pass/fail
✅ **Reusable**: Same engine for any rule type

## Step-by-Step Migration

### Step 1: Update Your Policy JSONs

Convert your existing policy criteria to the new format.

**Example converter function:**
```python
def convert_old_policy_to_new(old_policy):
    """Convert old policy format to new format"""
    new_criteria = []
    
    for rule in old_policy.get("criteria", []):
        checks = rule.get("checks", {})
        conditions = []
        
        # Convert min_symptom_duration_weeks
        if "min_symptom_duration_weeks" in checks and checks["min_symptom_duration_weeks"]:
            conditions.append({
                "field": "symptom_duration_weeks",
                "operator": "gte",
                "value": checks["min_symptom_duration_weeks"]
            })
        
        # Convert required_diagnoses
        if "required_diagnoses" in checks and checks["required_diagnoses"]:
            conditions.append({
                "field": "diagnoses",
                "operator": "any_in",
                "value": checks["required_diagnoses"]
            })
        
        # Convert min_pt_weeks
        if "min_pt_weeks" in checks and checks["min_pt_weeks"]:
            conditions.append({
                "field": "pt_completed_weeks",
                "operator": "gte",
                "value": checks["min_pt_weeks"]
            })
        
        new_criteria.append({
            "id": rule.get("id"),
            "description": rule.get("description"),
            "logic": "all",
            "conditions": conditions
        })
    
    return {"criteria": new_criteria}
```

### Step 2: Test with Both Systems

Run both old and new systems in parallel to verify results match:

```python
def compare_systems(patient_data, policy_data):
    # Old system
    old_patient = old_normalize_patient_evidence(patient_data)
    old_policy = old_normalize_policy_criteria(policy_data)
    old_results = old_evaluate_all(old_patient, old_policy)
    
    # New system
    new_patient = normalize_patient_evidence(patient_data)
    new_policy = normalize_policy_criteria(policy_data)
    new_results = evaluate_all(new_patient, new_policy)
    
    # Compare
    old_decision = all(r["met"] for r in old_results)
    new_decision = new_results["all_criteria_met"]
    
    if old_decision != new_decision:
        print("⚠️  WARNING: Results differ!")
        print(f"Old: {old_decision}, New: {new_decision}")
    else:
        print("✓ Results match")
    
    return old_decision == new_decision
```

### Step 3: Customize Normalization

Update `normalize_patient_evidence()` and `normalize_policy_criteria()` for your specific JSON structures.

**Common patterns:**

```python
# Your field is nested deeper
if "patient_info" in evidence:
    normalized["age"] = evidence["patient_info"]["demographics"]["age"]

# Your field has a different name
normalized["diagnoses"] = evidence.get("icd10_codes", [])

# Your field needs transformation
duration_days = evidence.get("symptom_duration_days")
if duration_days:
    normalized["symptom_duration_weeks"] = duration_days / 7
```

### Step 4: Add New Rule Types

Now you can easily add new types of checks:

```python
# In your policy JSON:
{
  "id": "bmi_check",
  "description": "BMI must be between 18.5 and 30",
  "conditions": [
    {
      "field": "bmi",
      "operator": "gte",
      "value": 18.5
    },
    {
      "field": "bmi",
      "operator": "lte",
      "value": 30
    }
  ]
}
```

```python
# OR logic example:
{
  "id": "alternative_treatments",
  "description": "Must try PT OR medications",
  "logic": "any",
  "conditions": [
    {"field": "pt_completed_weeks", "operator": "gte", "value": 6},
    {"field": "medication_trial", "operator": "eq", "value": true}
  ]
}
```

## Breaking Changes

⚠️ **Important differences to note:**

1. **Response structure changed:**
   - Old: `[{rule_id, description, met}, ...]`
   - New: `{results: [...], all_criteria_met: bool, total_rules: int, ...}`

2. **Normalization output:**
   - Old: Multiple separate fields
   - New: Single flat dictionary

3. **Null handling:**
   - Old: Explicitly checked for `None`
   - New: Automatically returns `False` for missing fields

## Testing Checklist

Before fully migrating:

- [ ] Test with 10+ real patient cases
- [ ] Test with all edge cases (missing data, null values)
- [ ] Test with multiple diagnoses
- [ ] Test OR logic scenarios
- [ ] Test range conditions
- [ ] Verify performance (should be similar or better)
- [ ] Update API documentation
- [ ] Update frontend to handle new response format

## Rollback Plan

If you need to rollback:

1. Keep old code files in `legacy/` directory
2. Use feature flag to switch between systems:

```python
USE_NEW_RULES_ENGINE = os.getenv("USE_NEW_RULES_ENGINE", "false") == "true"

if USE_NEW_RULES_ENGINE:
    from rules.rule_engine import evaluate_all
else:
    from legacy.rule_engine import evaluate_all
```

## Common Issues

### Issue: "Field not found"
**Solution:** Update `normalize_patient_evidence()` to extract that field

### Issue: "All rules failing"
**Solution:** Check that field names match between normalization and conditions

### Issue: "Wrong results"
**Solution:** Verify operator is correct (`gte` vs `gt`, `any_in` vs `contains`)

## Getting Help

1. Check `test_rules.py` for working examples
2. Check `test_edge_cases.py` for complex scenarios
3. Review `README.md` for full documentation
4. Add debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In rule_engine.py
print(f"Evaluating: {condition}")
print(f"Patient value: {patient_value}")
print(f"Result: {result}")
```

## Next Steps After Migration

1. Add rule versioning (track changes over time)
2. Build rule editor UI (no-code rule creation)
3. Add audit logging (who approved what, when)
4. Implement rule simulation (test before deploying)
5. Create rule templates (common patterns)