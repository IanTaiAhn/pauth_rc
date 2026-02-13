"""
Debug script to understand Utah Medicaid normalization issue
"""

import json
import sys
sys.path.insert(0, 'backend')

from app.normalization.normalized_custom import normalize_policy_criteria

# Load the actual Utah Medicaid policy from the diagnostic artifact
with open('api_artifacts/diagnostic_artifact_2.json', 'r') as f:
    artifact = json.load(f)

raw_policy = artifact['diagnostics']['raw_policy']

print("=" * 80)
print("INPUT: Raw Policy from Diagnostic Artifact")
print("=" * 80)
print(f"Payer: {raw_policy['rules']['payer']}")
print(f"CPT: {raw_policy['rules']['cpt_code']}")
print()

coverage = raw_policy['rules']['coverage_criteria']
print("Prerequisites:")
for p in coverage['prerequisites']:
    print(f"  - {p}")
print()

print("Clinical Indications:")
for c in coverage['clinical_indications']:
    print(f"  - {c}")
print()

print("=" * 80)
print("TEST 1: Format 1 (Full wrapper - what RAG pipeline returns)")
print("=" * 80)

# Run the normalization with Format 1 (full wrapper)
normalized_rules_format1 = normalize_policy_criteria(raw_policy)

print(f"\nGenerated {len(normalized_rules_format1)} rules:")
print()

for rule in normalized_rules_format1:
    print(f"[{rule['id']}] {rule['description']}")
    print(f"  Logic: {rule.get('logic', 'N/A')}")
    print(f"  Conditions:")
    for cond in rule['conditions']:
        print(f"    - {cond['field']} {cond['operator']} {cond['value']}")
    print()

print("=" * 80)
print("TEST 2: Format 2 (Direct policy object - what orchestration passes)")
print("=" * 80)

# Simulate what orchestration.py does: extract just the "rules" dict
policy_json = raw_policy.get("rules", {})

# Run normalization with Format 2
normalized_rules_format2 = normalize_policy_criteria(policy_json)

print(f"\nGenerated {len(normalized_rules_format2)} rules:")
print()

for rule in normalized_rules_format2:
    print(f"[{rule['id']}] {rule['description']}")
    print(f"  Logic: {rule.get('logic', 'N/A')}")
    print(f"  Conditions:")
    for cond in rule['conditions']:
        print(f"    - {cond['field']} {cond['operator']} {cond['value']}")
    print()

print("=" * 80)
print("EXPECTED RULES")
print("=" * 80)
print("Should have generated rules for:")
print("  1. X-ray requirement (from 'Prior X-rays or bone scan if available')")
print("  2. Physical therapy (from '6 weeks physical therapy')")
print("  3. Recent clinical notes (from 'Clinical notes within 30 days')")
print("  4. Evidence quality (always included)")
print()
print(f"Format 1 generated: {len(normalized_rules_format1)} rules")
print(f"Format 2 generated: {len(normalized_rules_format2)} rules")
print()

if len(normalized_rules_format2) >= 3:
    print("✅ SUCCESS: Format 2 now generates clinical rules!")
else:
    print("❌ FAILURE: Format 2 still not generating enough rules")
