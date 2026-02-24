"""
Structural + semantic validation for compiled policy checklists.
Catches both missing fields and logic inconsistencies (e.g. all vs count_gte mismatch).
"""

import re


VALID_REQUIREMENT_TYPES = {"any", "all", "count_gte"}
VALID_INPUT_TYPES = {"checkbox", "date", "number", "text", "checkbox_with_detail"}


def validate(template: dict) -> list[str]:
    """
    Validate a compiled checklist dict.

    Runs structural checks (required fields, valid enum values) and semantic
    checks (description language matches requirement_type, threshold range, etc.).

    Returns a list of error strings. Empty list means the template is valid.
    """
    errors: list[str] = []

    # --- Top-level required fields ---
    for field in ("payer", "cpt_code", "checklist_sections"):
        if field not in template:
            errors.append(f"Missing required top-level field: '{field}'")

    # --- checklist_sections ---
    sections = template.get("checklist_sections")
    if not isinstance(sections, list):
        errors.append("'checklist_sections' must be a list")
        sections = []

    section_ids: set[str] = set()

    for i, section in enumerate(sections):
        section_id = section.get("id", f"<section[{i}]>")
        prefix = f"Section '{section_id}'"
        section_ids.add(section_id)

        for field in ("id", "title", "description", "requirement_type", "items"):
            if field not in section:
                errors.append(f"{prefix}: missing required field '{field}'")

        req_type = section.get("requirement_type")
        if req_type and req_type not in VALID_REQUIREMENT_TYPES:
            errors.append(
                f"{prefix}: invalid requirement_type '{req_type}'. "
                f"Must be one of: {sorted(VALID_REQUIREMENT_TYPES)}"
            )

        # Structural: count_gte requires threshold
        if req_type == "count_gte":
            threshold = section.get("threshold")
            if threshold is None:
                errors.append(f"{prefix}: requirement_type 'count_gte' requires a 'threshold' field")
            elif not isinstance(threshold, (int, float)):
                errors.append(f"{prefix}: 'threshold' must be a number")

        # Semantic: description language vs requirement_type
        description = section.get("description", "")
        errors.extend(_semantic_check(prefix, description, req_type, section))

        # Validate items
        items = section.get("items")
        if not isinstance(items, list):
            errors.append(f"{prefix}: 'items' must be a list")
            continue
        errors.extend(_validate_items(prefix, items))

    # --- exception_pathways ---
    exceptions = template.get("exception_pathways", [])
    if not isinstance(exceptions, list):
        errors.append("'exception_pathways' must be a list")
        exceptions = []

    for i, exception in enumerate(exceptions):
        exc_id = exception.get("id", f"<exception[{i}]>")
        prefix = f"Exception '{exc_id}'"

        for field in ("id", "title", "waives", "requirement_type", "items"):
            if field not in exception:
                errors.append(f"{prefix}: missing required field '{field}'")

        waives = exception.get("waives", [])
        if not isinstance(waives, list):
            errors.append(f"{prefix}: 'waives' must be a list")
        else:
            if len(waives) == 0:
                errors.append(f"{prefix}: 'waives' list must not be empty")
            for waived_id in waives:
                if waived_id not in section_ids:
                    errors.append(f"{prefix}: waives unknown section_id '{waived_id}'")

        req_type = exception.get("requirement_type")
        if req_type == "count_gte" and exception.get("threshold") is None:
            errors.append(f"{prefix}: requirement_type 'count_gte' requires a 'threshold' field")

        items = exception.get("items")
        if isinstance(items, list):
            errors.extend(_validate_items(prefix, items))

    # --- exclusions ---
    exclusions = template.get("exclusions", [])
    if not isinstance(exclusions, list):
        errors.append("'exclusions' must be a list")

    # --- lists ---
    for field in ("denial_prevention_tips", "submission_reminders"):
        if field in template and not isinstance(template[field], list):
            errors.append(f"'{field}' must be a list")

    return errors


def _validate_items(section_prefix: str, items: list) -> list[str]:
    errors: list[str] = []
    for j, item in enumerate(items):
        item_prefix = f"{section_prefix} item[{j}]"
        if not isinstance(item, dict):
            errors.append(f"{item_prefix}: must be an object")
            continue
        for field in ("field", "label", "input_type"):
            if field not in item:
                errors.append(f"{item_prefix}: missing required field '{field}'")
        input_type = item.get("input_type")
        if input_type and input_type not in VALID_INPUT_TYPES:
            errors.append(
                f"{item_prefix}: invalid input_type '{input_type}'. "
                f"Must be one of: {sorted(VALID_INPUT_TYPES)}"
            )
    return errors


def _semantic_check(prefix: str, description: str, req_type: str, section: dict) -> list[str]:
    """
    Check that the description language is consistent with requirement_type.
    Catches the all vs count_gte mismatch.
    """
    errors: list[str] = []
    desc_lower = description.lower()

    # "at least N of" or "at least N" with a number → should be count_gte
    if re.search(r"at least \d+", desc_lower) and req_type != "count_gte":
        errors.append(
            f"{prefix}: description says 'at least N' but requirement_type is '{req_type}' "
            f"(expected 'count_gte')"
        )

    # "all of" → should be all
    if re.search(r"\ball of\b", desc_lower) and req_type not in ("all",):
        errors.append(
            f"{prefix}: description says 'all of' but requirement_type is '{req_type}' "
            f"(expected 'all')"
        )

    # count_gte threshold should not exceed number of items
    if req_type == "count_gte":
        threshold = section.get("threshold")
        items = section.get("items", [])
        if threshold is not None and isinstance(threshold, (int, float)) and threshold > len(items):
            errors.append(
                f"{prefix}: threshold {threshold} exceeds number of items ({len(items)})"
            )

    return errors
