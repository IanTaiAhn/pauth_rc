"""
Step 1 of the two-step pipeline: policy text → checklist skeleton.

Sends the policy to the LLM with a structure-focused prompt.
The output is a skeleton dict with sections, requirement types,
exception pathways, and exclusions — but no detail fields yet.
"""

import logging

from app.llm import GroqClient
from app.prompts.structure_prompt import build_structure_prompt

logger = logging.getLogger(__name__)


def create_skeleton(policy_text: str, payer: str, cpt_code: str) -> dict:
    """
    Call the LLM to identify the logical structure of the policy.

    Returns a dict with:
      - checklist_sections
      - exception_pathways
      - exclusions

    Raises ValueError if the LLM returns nothing or unparseable JSON.
    """
    client = GroqClient()
    prompt = build_structure_prompt(policy_text, payer, cpt_code)

    logger.info("Step 1 — structuring policy for payer=%s cpt=%s", payer, cpt_code)
    skeleton = client.generate_json(prompt, max_tokens=4096)

    if skeleton is None:
        raise ValueError("Step 1 (structurer): LLM returned no parseable JSON")

    # Inject payer/cpt so the skeleton carries identity through the pipeline
    skeleton["payer"] = payer
    skeleton["cpt_code"] = cpt_code

    logger.info(
        "Step 1 complete — %d sections, %d exceptions, %d exclusions",
        len(skeleton.get("checklist_sections", [])),
        len(skeleton.get("exception_pathways", [])),
        len(skeleton.get("exclusions", [])),
    )
    return skeleton
