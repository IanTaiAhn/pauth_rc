"""
Unit tests for count_gte and count_lte logic operators in rule_engine.evaluate_rule(),
and for the rule evaluation order in evaluate_all() (exclusions → exceptions → standard).
"""

import pytest
from app.rules.rule_engine import evaluate_rule, evaluate_all


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conditions(n: int) -> list[dict]:
    """Return n conditions that check field_i == True."""
    return [{"field": f"field_{i}", "operator": "eq", "value": True} for i in range(n)]


def _patient_with_true_fields(*indices: int) -> dict:
    """Return patient data where exactly the listed field indices are True."""
    return {f"field_{i}": True for i in indices}


# ---------------------------------------------------------------------------
# count_gte — threshold = 1
# ---------------------------------------------------------------------------

class TestCountGteThreshold1:
    def test_zero_of_three_pass_fails(self):
        rule = {"id": "r", "logic": "count_gte", "threshold": 1, "conditions": _make_conditions(3)}
        result = evaluate_rule({}, rule)
        assert result["met"] is False

    def test_exactly_one_of_three_passes(self):
        rule = {"id": "r", "logic": "count_gte", "threshold": 1, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0)
        result = evaluate_rule(patient, rule)
        assert result["met"] is True

    def test_two_of_three_pass(self):
        rule = {"id": "r", "logic": "count_gte", "threshold": 1, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0, 1)
        result = evaluate_rule(patient, rule)
        assert result["met"] is True

    def test_all_three_pass(self):
        rule = {"id": "r", "logic": "count_gte", "threshold": 1, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0, 1, 2)
        result = evaluate_rule(patient, rule)
        assert result["met"] is True


# ---------------------------------------------------------------------------
# count_gte — threshold = 2
# ---------------------------------------------------------------------------

class TestCountGteThreshold2:
    def test_zero_pass_fails(self):
        rule = {"id": "r", "logic": "count_gte", "threshold": 2, "conditions": _make_conditions(3)}
        result = evaluate_rule({}, rule)
        assert result["met"] is False

    def test_one_pass_is_one_fewer_than_threshold_fails(self):
        """Exactly threshold-1 conditions pass — edge case that must fail."""
        rule = {"id": "r", "logic": "count_gte", "threshold": 2, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0)
        result = evaluate_rule(patient, rule)
        assert result["met"] is False

    def test_exactly_threshold_two_pass(self):
        """Exactly threshold conditions pass — edge case that must pass."""
        rule = {"id": "r", "logic": "count_gte", "threshold": 2, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0, 1)
        result = evaluate_rule(patient, rule)
        assert result["met"] is True

    def test_all_three_pass(self):
        rule = {"id": "r", "logic": "count_gte", "threshold": 2, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0, 1, 2)
        result = evaluate_rule(patient, rule)
        assert result["met"] is True


# ---------------------------------------------------------------------------
# count_lte — threshold = 1
# ---------------------------------------------------------------------------

class TestCountLteThreshold1:
    def test_zero_pass(self):
        rule = {"id": "r", "logic": "count_lte", "threshold": 1, "conditions": _make_conditions(3)}
        result = evaluate_rule({}, rule)
        assert result["met"] is True

    def test_exactly_threshold_one_pass(self):
        """Exactly threshold conditions pass — edge case that must pass."""
        rule = {"id": "r", "logic": "count_lte", "threshold": 1, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0)
        result = evaluate_rule(patient, rule)
        assert result["met"] is True

    def test_two_pass_is_one_more_than_threshold_fails(self):
        """threshold+1 conditions pass — edge case that must fail."""
        rule = {"id": "r", "logic": "count_lte", "threshold": 1, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0, 1)
        result = evaluate_rule(patient, rule)
        assert result["met"] is False

    def test_all_three_pass_fails(self):
        rule = {"id": "r", "logic": "count_lte", "threshold": 1, "conditions": _make_conditions(3)}
        patient = _patient_with_true_fields(0, 1, 2)
        result = evaluate_rule(patient, rule)
        assert result["met"] is False


# ---------------------------------------------------------------------------
# count_lte — threshold = 2
# ---------------------------------------------------------------------------

class TestCountLteThreshold2:
    def test_zero_pass(self):
        rule = {"id": "r", "logic": "count_lte", "threshold": 2, "conditions": _make_conditions(4)}
        result = evaluate_rule({}, rule)
        assert result["met"] is True

    def test_one_pass(self):
        rule = {"id": "r", "logic": "count_lte", "threshold": 2, "conditions": _make_conditions(4)}
        patient = _patient_with_true_fields(0)
        result = evaluate_rule(patient, rule)
        assert result["met"] is True

    def test_exactly_threshold_two_pass(self):
        """Exactly threshold conditions pass — edge case that must pass."""
        rule = {"id": "r", "logic": "count_lte", "threshold": 2, "conditions": _make_conditions(4)}
        patient = _patient_with_true_fields(0, 1)
        result = evaluate_rule(patient, rule)
        assert result["met"] is True

    def test_three_pass_is_one_more_than_threshold_fails(self):
        """threshold+1 conditions pass — edge case that must fail."""
        rule = {"id": "r", "logic": "count_lte", "threshold": 2, "conditions": _make_conditions(4)}
        patient = _patient_with_true_fields(0, 1, 2)
        result = evaluate_rule(patient, rule)
        assert result["met"] is False


# ---------------------------------------------------------------------------
# Existing operators are unchanged
# ---------------------------------------------------------------------------

class TestExistingOperatorsUnchanged:
    def test_all_passes_when_all_met(self):
        rule = {"id": "r", "logic": "all", "conditions": _make_conditions(2)}
        result = evaluate_rule(_patient_with_true_fields(0, 1), rule)
        assert result["met"] is True

    def test_all_fails_when_one_missing(self):
        rule = {"id": "r", "logic": "all", "conditions": _make_conditions(2)}
        result = evaluate_rule(_patient_with_true_fields(0), rule)
        assert result["met"] is False

    def test_any_passes_when_one_met(self):
        rule = {"id": "r", "logic": "any", "conditions": _make_conditions(2)}
        result = evaluate_rule(_patient_with_true_fields(0), rule)
        assert result["met"] is True

    def test_any_fails_when_none_met(self):
        rule = {"id": "r", "logic": "any", "conditions": _make_conditions(2)}
        result = evaluate_rule({}, rule)
        assert result["met"] is False


# ---------------------------------------------------------------------------
# evaluate_all — evaluation order
# ---------------------------------------------------------------------------

class TestEvaluateAllOrder:
    """Tests for the exclusion → exception → standard rule evaluation order."""

    def _make_eq_condition(self, field: str, value) -> dict:
        return {"field": field, "operator": "eq", "value": value}

    def test_exclusion_rule_triggers_excluded_result(self):
        """An exclusion rule that passes must return excluded=True immediately."""
        rules = [
            {
                "id": "excl_rule",
                "description": "Excluded if flagged",
                "logic": "all",
                "exclusion": True,
                "conditions": [self._make_eq_condition("is_excluded", True)],
            },
            {
                "id": "standard_rule",
                "description": "Standard",
                "logic": "all",
                "conditions": [self._make_eq_condition("criteria_met", True)],
            },
        ]
        patient = {"is_excluded": True, "criteria_met": True}
        result = evaluate_all(patient, rules)
        assert result["excluded"] is True
        assert result["all_criteria_met"] is False

    def test_exclusion_rule_not_triggered_continues_to_standard(self):
        """When no exclusion rule passes, standard rules are still evaluated."""
        rules = [
            {
                "id": "excl_rule",
                "description": "Excluded if flagged",
                "logic": "all",
                "exclusion": True,
                "conditions": [self._make_eq_condition("is_excluded", True)],
            },
            {
                "id": "standard_rule",
                "description": "Standard",
                "logic": "all",
                "conditions": [self._make_eq_condition("criteria_met", True)],
            },
        ]
        patient = {"is_excluded": False, "criteria_met": True}
        result = evaluate_all(patient, rules)
        assert result["excluded"] is False
        assert result["all_criteria_met"] is True

    def test_exception_rule_waives_standard_rule(self):
        """When an exception rule passes, its overrides list exempts the named standard rules."""
        rules = [
            {
                "id": "exception_red_flag",
                "description": "Red flag waives conservative treatment",
                "logic": "all",
                "exception_pathway": True,
                "overrides": ["conservative_treatment"],
                "conditions": [self._make_eq_condition("red_flag", True)],
            },
            {
                "id": "conservative_treatment",
                "description": "6 weeks PT required",
                "logic": "all",
                "conditions": [self._make_eq_condition("pt_weeks_gte_6", True)],
            },
            {
                "id": "clinical_indication",
                "description": "Must have clinical indication",
                "logic": "all",
                "conditions": [self._make_eq_condition("has_indication", True)],
            },
        ]
        # Red flag present, no PT, but has indication — conservative_treatment is waived
        patient = {"red_flag": True, "pt_weeks_gte_6": False, "has_indication": True}
        result = evaluate_all(patient, rules)
        assert result["excluded"] is False
        assert "conservative_treatment" in result["active_overrides"]
        # conservative_treatment is waived, so all remaining rules pass
        assert result["all_criteria_met"] is True

    def test_exception_rule_does_not_waive_when_it_fails(self):
        """When an exception rule does not pass, no overrides are applied."""
        rules = [
            {
                "id": "exception_red_flag",
                "description": "Red flag waives conservative treatment",
                "logic": "all",
                "exception_pathway": True,
                "overrides": ["conservative_treatment"],
                "conditions": [self._make_eq_condition("red_flag", True)],
            },
            {
                "id": "conservative_treatment",
                "description": "6 weeks PT required",
                "logic": "all",
                "conditions": [self._make_eq_condition("pt_weeks_gte_6", True)],
            },
        ]
        # No red flag — exception does not fire, conservative_treatment is evaluated normally
        patient = {"red_flag": False, "pt_weeks_gte_6": False}
        result = evaluate_all(patient, rules)
        assert result["excluded"] is False
        assert result["active_overrides"] == []
        assert result["all_criteria_met"] is False

    def test_active_overrides_listed_in_return(self):
        """active_overrides in the return value lists all waived rule IDs."""
        rules = [
            {
                "id": "exception_tumor",
                "logic": "all",
                "exception_pathway": True,
                "overrides": ["rule_a", "rule_b"],
                "conditions": [self._make_eq_condition("tumor_suspected", True)],
            },
            {
                "id": "rule_a",
                "logic": "all",
                "conditions": [self._make_eq_condition("a", True)],
            },
            {
                "id": "rule_b",
                "logic": "all",
                "conditions": [self._make_eq_condition("b", True)],
            },
        ]
        patient = {"tumor_suspected": True, "a": False, "b": False}
        result = evaluate_all(patient, rules)
        assert set(result["active_overrides"]) == {"rule_a", "rule_b"}
        assert result["all_criteria_met"] is True  # no non-waived standard rules remain
