"""
Orchestrates the policy compilation pipeline:
  load_skeleton → detailer → validate → save

This is the only entry point for compiling a policy document.
"""

import json
import logging
import os
from pathlib import Path

from app.prompts.detail_prompt import build_detail_prompt
from app.llm import GroqClient
from app.validation import validate

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "./templates"))
_SKELETONS_DIR = Path(os.environ.get("SKELETONS_DIR", "./api_artifacts"))


def compile(policy_text: str, payer: str, lcd_code: str, include_debug: bool = False) -> dict:
    """
    Compile a payer policy document into a filled checklist.

    Loads a pre-built skeleton JSON from the skeletons directory and feeds it
    along with the policy text into the detail extractor.

    Args:
        policy_text: Full text of the payer policy document.
        payer:       Payer identifier (e.g. "medicare").
        lcd_code:    LCD code string (e.g. "L36007").
        include_debug: If True, collect prompts and raw responses from the detail step.

    Returns:
        A dict with keys:
        - "template": PolicyTemplate dict
        - "debug": dict with step2_detail info (only if include_debug=True)
    """
    # Load pre-built skeleton
    skeleton = _load_skeleton(lcd_code, payer)

    # Fill details
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
    if include_debug and step2_debug:
        result["debug"] = {"step2_detail": step2_debug}

    return result


def _load_skeleton(lcd_code: str, payer: str) -> dict:
    """Load a pre-built skeleton JSON from the skeletons directory."""
    skeleton_path = _SKELETONS_DIR / f"{lcd_code.lower()}_skeleton.json"
    if not skeleton_path.exists():
        raise FileNotFoundError(
            f"Skeleton file not found: {skeleton_path}. "
            f"Expected at {_SKELETONS_DIR}/{lcd_code.lower()}_skeleton.json"
        )
    with open(skeleton_path, "r", encoding="utf-8") as fh:
        skeleton = json.load(fh)

    # Ensure identity fields are set
    skeleton.setdefault("payer", payer)
    skeleton.setdefault("lcd_code", lcd_code)

    logger.info(
        "Loaded skeleton from %s — %d sections, %d exceptions, %d exclusions",
        skeleton_path,
        len(skeleton.get("checklist_sections", [])),
        len(skeleton.get("exception_pathways", [])),
        len(skeleton.get("exclusions", [])),
    )
    return skeleton


def _fill_details_with_debug(policy_text: str, skeleton: dict) -> tuple[dict, dict]:
    """Detail step with debug collection."""
    client = GroqClient()
    prompt = build_detail_prompt(policy_text, skeleton)

    logger.info("Detailing policy for payer=%s lcd=%s", skeleton.get("payer"), skeleton.get("lcd_code"))
    filled, raw_response = client.generate_json_with_debug(prompt, max_tokens=4096)

    if filled is None:
        raise ValueError("Detailer: LLM returned no parseable JSON")

    filled.setdefault("payer", skeleton.get("payer"))
    filled.setdefault("lcd_code", skeleton.get("lcd_code"))
    filled.setdefault("denial_prevention_tips", [])
    filled.setdefault("submission_reminders", [])

    logger.info("Detail step complete — checklist filled")

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
