#!/usr/bin/env python3
"""
Structural validator for P-Auth RC compiled rules.

Validates that:
1. Every field in canonical_rules exists in the domain registry
2. Every field in canonical_rules exists in the extraction_schema
3. Every override target references an existing rule ID
4. count_gte/count_lte rules have thresholds
5. Extraction schema has no orphan fields (not used by any rule)
6. No duplicate rule IDs
7. Exclusion rules are not referenced in overrides

Usage:
    python validate_rules.py --registry knee_mri.registry.json --rules utah_medicaid_73721.rules.json
"""

import json
import sys
import argparse
from pathlib import Path
from difflib import get_close_matches


def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def validate(registry: dict, rules: dict) -> list[dict]:
    """Run all validation checks. Returns list of issues."""
    issues = []

    # Extract registry field names (skip _comment keys)
    registry_fields = {
        k for k in registry.get("fields", {}).keys()
        if not k.startswith("_")
    }

    # Extract rule data
    canonical_rules = rules.get("canonical_rules", [])
    extraction_schema = rules.get("extraction_schema", {})
    schema_fields = {k for k in extraction_schema.keys() if not k.startswith("_")}

    rule_ids = set()
    all_condition_fields = set()
    exception_override_targets = set()
    exclusion_ids = set()

    # ── Check 0: Domain version match ──
    rules_domain_version = rules.get("domain_registry_version")
    registry_version = registry.get("version")
    if rules_domain_version and registry_version:
        if rules_domain_version != registry_version:
            issues.append({
                "severity": "WARNING",
                "check": "domain_version",
                "message": f"Rules reference registry v{rules_domain_version} but registry is v{registry_version}"
            })

    for rule in canonical_rules:
        rule_id = rule.get("id", "<missing>")

        # ── Check 1: Duplicate rule IDs ──
        if rule_id in rule_ids:
            issues.append({
                "severity": "ERROR",
                "check": "duplicate_rule_id",
                "rule": rule_id,
                "message": f"Duplicate rule ID: '{rule_id}'"
            })
        rule_ids.add(rule_id)

        # Track exclusion IDs
        if rule.get("exclusion"):
            exclusion_ids.add(rule_id)

        # ── Check 2: count_gte/count_lte must have threshold ──
        logic = rule.get("logic", "")
        if logic in ("count_gte", "count_lte"):
            if "threshold" not in rule:
                issues.append({
                    "severity": "ERROR",
                    "check": "missing_threshold",
                    "rule": rule_id,
                    "message": f"Rule '{rule_id}' uses '{logic}' but has no 'threshold' field"
                })
            else:
                threshold = rule["threshold"]
                num_conditions = len(rule.get("conditions", []))
                if logic == "count_gte" and threshold > num_conditions:
                    issues.append({
                        "severity": "ERROR",
                        "check": "impossible_threshold",
                        "rule": rule_id,
                        "message": f"Rule '{rule_id}': threshold {threshold} > {num_conditions} conditions (can never pass)"
                    })

        # ── Check 3: Every condition field exists in registry ──
        for cond in rule.get("conditions", []):
            field = cond.get("field")
            if field:
                all_condition_fields.add(field)

                if field not in registry_fields:
                    suggestion = get_close_matches(field, registry_fields, n=1, cutoff=0.6)
                    hint = f" Did you mean '{suggestion[0]}'?" if suggestion else ""
                    issues.append({
                        "severity": "ERROR",
                        "check": "field_not_in_registry",
                        "rule": rule_id,
                        "field": field,
                        "message": f"Rule '{rule_id}': field '{field}' not found in domain registry.{hint}"
                    })

                if field not in schema_fields:
                    issues.append({
                        "severity": "ERROR",
                        "check": "field_not_in_extraction_schema",
                        "rule": rule_id,
                        "field": field,
                        "message": f"Rule '{rule_id}': field '{field}' not in extraction_schema (LLM won't extract it)"
                    })

        # ── Check 4: Override targets exist ──
        for target in rule.get("overrides", []):
            exception_override_targets.add(target)
            if target not in {r.get("id") for r in canonical_rules}:
                issues.append({
                    "severity": "ERROR",
                    "check": "override_target_missing",
                    "rule": rule_id,
                    "target": target,
                    "message": f"Rule '{rule_id}': overrides '{target}' but no rule with that ID exists"
                })

    # ── Check 5: Orphan fields in extraction schema ──
    orphan_fields = schema_fields - all_condition_fields
    for field in orphan_fields:
        issues.append({
            "severity": "WARNING",
            "check": "orphan_schema_field",
            "field": field,
            "message": f"Extraction schema field '{field}' is not used in any rule condition (LLM will extract it but nothing evaluates it)"
        })

    # ── Check 6: Exclusions should not appear in overrides ──
    overridden_exclusions = exclusion_ids & exception_override_targets
    for eid in overridden_exclusions:
        issues.append({
            "severity": "WARNING",
            "check": "exclusion_in_overrides",
            "rule": eid,
            "message": f"Exclusion rule '{eid}' appears in an exception's overrides list — exclusions typically cannot be waived"
        })

    # ── Check 7: Exception rules must have overrides ──
    for rule in canonical_rules:
        if rule.get("exception_pathway") and not rule.get("overrides"):
            issues.append({
                "severity": "WARNING",
                "check": "exception_without_overrides",
                "rule": rule.get("id"),
                "message": f"Exception rule '{rule.get('id')}' has exception_pathway=true but no overrides list"
            })

    return issues


def print_report(issues: list[dict], registry_path: str, rules_path: str):
    errors = [i for i in issues if i["severity"] == "ERROR"]
    warnings = [i for i in issues if i["severity"] == "WARNING"]

    print("=" * 70)
    print("P-Auth RC — Rule Validation Report")
    print(f"Registry: {registry_path}")
    print(f"Rules:    {rules_path}")
    print("=" * 70)

    if not issues:
        print("\n✅ ALL CHECKS PASSED — no errors or warnings\n")
        return

    if errors:
        print(f"\n❌ {len(errors)} ERROR(S):\n")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. [{err['check']}] {err['message']}")

    if warnings:
        print(f"\n⚠️  {len(warnings)} WARNING(S):\n")
        for i, warn in enumerate(warnings, 1):
            print(f"  {i}. [{warn['check']}] {warn['message']}")

    print()
    if errors:
        print(f"❌ VALIDATION FAILED — {len(errors)} error(s) must be fixed before deployment")
    else:
        print(f"⚠️  VALIDATION PASSED WITH WARNINGS — review warnings before deployment")
    print()


def main():
    parser = argparse.ArgumentParser(description="Validate P-Auth RC compiled rules")
    parser.add_argument("--registry", required=True, help="Path to domain registry JSON")
    parser.add_argument("--rules", required=True, help="Path to payer rules JSON")
    parser.add_argument("--json", action="store_true", help="Output issues as JSON")
    args = parser.parse_args()

    registry = load_json(args.registry)
    rules = load_json(args.rules)
    issues = validate(registry, rules)

    if args.json:
        print(json.dumps(issues, indent=2))
    else:
        print_report(issues, args.registry, args.rules)

    sys.exit(1 if any(i["severity"] == "ERROR" for i in issues) else 0)


if __name__ == "__main__":
    main()
