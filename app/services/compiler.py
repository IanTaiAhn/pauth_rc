"""
Orchestrates the two-step policy compilation pipeline:
  structurer → detailer → validate → save

This is the only entry point for compiling a policy document.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from app.llm import GroqClient
from app.prompts.structure_prompt import build_structure_prompt
from app.prompts.detail_prompt import build_detail_prompt
from app.validation import validate
from app.schemas import CompilationDebug, StepDebugInfo

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "./templates"))


def compile(policy_text: str, payer: str, lcd_code: str, include_debug: bool = False) -> dict:
    """
    Compile a payer policy document into a filled checklist.

    Args:
        policy_text: Full text of the payer policy document.
        payer:       Payer identifier (e.g. "medicare").
        lcd_code:    LCD code string (e.g. "L36007").
        include_debug: If True, collect prompts and raw responses.

    Returns:
        A dict with keys:
        - "template": PolicyTemplate dict
        - "debug": CompilationDebug dict (only if include_debug=True)
    """
    debug_info = None

    # Step 1: structure
    if include_debug:
        skeleton, step1_debug = _create_skeleton_with_debug(policy_text, payer, lcd_code)
    else:
        from app.services import structurer
        skeleton = structurer.create_skeleton(policy_text, payer, lcd_code)
        step1_debug = None

    # Step 2: fill details
    if include_debug:
        filled, step2_debug = _fill_details_with_debug(policy_text, skeleton)
    else:
        from app.services import detailer
        filled = detailer.fill_details(policy_text, skeleton)
        step2_debug = None

    # Validate
    errors = validate(filled)
    if errors:
        logger.warning(
            "%d validation error(s) for %s/%s — human review required",
            len(errors), payer, lcd_code,
        )
        for err in errors:
            logger.warning("  %s", err)

    filled["validation_errors"] = errors

    # Save
    _save(filled, payer, lcd_code)

    # Build response
    result = {"template": filled}
    if include_debug and step1_debug and step2_debug:
        result["debug"] = {
            "step1_structure": step1_debug,
            "step2_detail": step2_debug,
        }

    return result


def _create_skeleton_with_debug(policy_text: str, payer: str, lcd_code: str) -> tuple[dict, dict]:
    """Step 1 with debug collection."""
    client = GroqClient()
    prompt = build_structure_prompt(policy_text, payer, lcd_code)

    logger.info("Step 1 — structuring policy for payer=%s lcd=%s", payer, lcd_code)
    skeleton, raw_response = client.generate_json_with_debug(prompt, max_tokens=4096)

    if skeleton is None:
        raise ValueError("Step 1 (structurer): LLM returned no parseable JSON")

    skeleton["payer"] = payer
    skeleton["lcd_code"] = lcd_code

    logger.info(
        "Step 1 complete — %d sections, %d exceptions, %d exclusions",
        len(skeleton.get("checklist_sections", [])),
        len(skeleton.get("exception_pathways", [])),
        len(skeleton.get("exclusions", [])),
    )

    debug = {
        "step_name": "structure",
        "prompt": prompt,
        "raw_response": raw_response,
        "parsed_output": skeleton,
    }

    return skeleton, debug


def _fill_details_with_debug(policy_text: str, skeleton: dict) -> tuple[dict, dict]:
    """Step 2 with debug collection."""
    client = GroqClient()
    prompt = build_detail_prompt(policy_text, skeleton)

    logger.info("Step 2 — detailing policy for payer=%s lcd=%s", skeleton.get("payer"), skeleton.get("lcd_code"))
    filled, raw_response = client.generate_json_with_debug(prompt, max_tokens=4096)

    if filled is None:
        raise ValueError("Step 2 (detailer): LLM returned no parseable JSON")

    filled.setdefault("payer", skeleton.get("payer"))
    filled.setdefault("lcd_code", skeleton.get("lcd_code"))
    filled.setdefault("denial_prevention_tips", [])
    filled.setdefault("submission_reminders", [])

    logger.info("Step 2 complete — checklist filled")

    debug = {
        "step_name": "detail",
        "prompt": prompt,
        "raw_response": raw_response,
        "parsed_output": filled,
    }

    return filled, debug


def _save(result: dict, payer: str, lcd_code: str) -> None:
    _TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _TEMPLATES_DIR / f"{payer}_{lcd_code}.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    logger.info("Saved template to %s", output_path)
