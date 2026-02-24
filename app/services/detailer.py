"""
Step 2 of the two-step pipeline: skeleton + policy → filled checklist.

Sends the policy text and the Step 1 skeleton to the LLM with a
detail-focused prompt. The LLM fills in ICD-10 codes, timeframes,
help_text, denial tips, and submission reminders into the existing slots.
The structure is locked — the LLM only extracts details.
"""

import logging

from app.llm import GroqClient
from app.prompts.detail_prompt import build_detail_prompt

logger = logging.getLogger(__name__)


def fill_details(policy_text: str, skeleton: dict) -> dict:
    """
    Call the LLM to fill in detail fields from the policy into the skeleton.

    Returns a filled dict matching the PolicyTemplate schema.
    Raises ValueError if the LLM returns nothing or unparseable JSON.
    """
    client = GroqClient()
    prompt = build_detail_prompt(policy_text, skeleton)

    logger.info("Step 2 — detailing policy for payer=%s cpt=%s", skeleton.get("payer"), skeleton.get("cpt_code"))
    filled = client.generate_json(prompt, max_tokens=4096)

    if filled is None:
        raise ValueError("Step 2 (detailer): LLM returned no parseable JSON")

    # Preserve identity fields from skeleton in case LLM dropped them
    filled.setdefault("payer", skeleton.get("payer"))
    filled.setdefault("cpt_code", skeleton.get("cpt_code"))
    filled.setdefault("denial_prevention_tips", [])
    filled.setdefault("submission_reminders", [])

    logger.info("Step 2 complete — checklist filled")
    return filled
