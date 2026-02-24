"""
Orchestrates the two-step policy compilation pipeline:
  structurer → detailer → validate → save

This is the only entry point for compiling a policy document.
"""

import json
import logging
import os
from pathlib import Path

from app.services import structurer, detailer
from app.validation import validate

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "./templates"))


def compile(policy_text: str, payer: str, cpt_code: str) -> dict:
    """
    Compile a payer policy document into a filled checklist.

    Args:
        policy_text: Full text of the payer policy document.
        payer:       Payer identifier (e.g. "utah_medicaid").
        cpt_code:    CPT code string (e.g. "73721").

    Returns:
        A dict matching the PolicyTemplate schema, plus a
        "validation_errors" key (empty list if valid).
    """
    # Step 1: structure
    skeleton = structurer.create_skeleton(policy_text, payer, cpt_code)

    # Step 2: fill details
    filled = detailer.fill_details(policy_text, skeleton)

    # Validate
    errors = validate(filled)
    if errors:
        logger.warning(
            "%d validation error(s) for %s/%s — human review required",
            len(errors), payer, cpt_code,
        )
        for err in errors:
            logger.warning("  %s", err)

    filled["validation_errors"] = errors

    # Save
    _save(filled, payer, cpt_code)
    return filled


def _save(result: dict, payer: str, cpt_code: str) -> None:
    _TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _TEMPLATES_DIR / f"{payer}_{cpt_code}.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    logger.info("Saved template to %s", output_path)
