"""
Orchestration endpoint for schema-driven PA readiness check.

Pipeline (request time — PHI present):
1. Accept JSON body: chart_text (str), payer (str), cpt_code (str)
2. Load compiled rules from compiled_rules/{payer}_{cpt_code}.json — 404 if missing
3. Extract patient data via extract_evidence_schema_driven (Bedrock — BAA required)
4. Evaluate rules deterministically via rule_engine.evaluate_all
5. Return OrchestrationResponse with verdict, score, criteria, gaps, and next steps

HIPAA NOTE: chart_text contains PHI. The evidence extraction step routes only
through BAA-covered providers (AWS Bedrock). Groq must never receive chart text.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.evidence import extract_evidence_schema_driven
from app.rules.rule_engine import evaluate_all
from app.api_models.schemas import OrchestrationResponse, CriterionResult

logger = logging.getLogger(__name__)

router = APIRouter()

# Compiled rule sets live here — produced by compile_policy.py at index-build time
COMPILED_RULES_DIR = Path(__file__).resolve().parent.parent / "rag_pipeline" / "compiled_rules"

# Human-readable CPT labels
CPT_LABELS: dict[str, str] = {
    "73721": "MRI Knee Without Contrast",
    "73722": "MRI Knee With Contrast",
    "73723": "MRI Knee Without and With Contrast",
}

# Human-readable payer names
PAYER_LABELS: dict[str, str] = {
    "utah_medicaid": "Utah Medicaid",
    "aetna": "Aetna",
}


class CheckPriorAuthRequest(BaseModel):
    """Request body for the PA readiness check endpoint."""

    chart_text: str
    payer: str
    cpt_code: str


def _load_compiled_rules(payer: str, cpt_code: str) -> dict:
    """
    Load the compiled rule set for a payer/CPT combination.

    Args:
        payer: Payer identifier, e.g. "utah_medicaid".
        cpt_code: CPT code string, e.g. "73721".

    Returns:
        Parsed JSON dict with "canonical_rules" and "extraction_schema".

    Raises:
        HTTPException 404: No compiled rule set found for this combination.
    """
    path = COMPILED_RULES_DIR / f"{payer}_{cpt_code}.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"No compiled rules found for payer '{payer}' and CPT code '{cpt_code}'. "
                f"Run the policy compiler first: "
                f"compile_policy(policy_text, payer='{payer}', cpt_code='{cpt_code}')"
            ),
        )
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _derive_verdict(readiness_score: int, fail_count: int, excluded: bool) -> str:
    """
    Map score and failure count to a PA verdict label.

    Returns:
        "EXCLUDED"          — case is not eligible (e.g. workers' comp)
        "LIKELY_TO_APPROVE" — score >= 80 and zero failures
        "LIKELY_TO_DENY"    — score < 50 or 2+ failures
        "NEEDS_REVIEW"      — everything else
    """
    if excluded:
        return "EXCLUDED"
    if readiness_score >= 80 and fail_count == 0:
        return "LIKELY_TO_APPROVE"
    elif readiness_score < 50 or fail_count >= 2:
        return "LIKELY_TO_DENY"
    return "NEEDS_REVIEW"


def _generate_next_steps(gaps: list[str], exception_applied: str | None) -> str:
    """Generate plain-English guidance based on the gap list."""
    if not gaps:
        return "All criteria met. This chart is ready for PA submission."
    if len(gaps) == 1:
        step = "One criterion is unmet. Resolve the item in the gaps list before submitting."
    else:
        step = "Multiple criteria are unmet. Review the gaps list and update the chart before submitting."
    if exception_applied:
        step += f" Note: Exception pathway applied — {exception_applied}."
    return step


@router.post("/check_prior_auth", response_model=OrchestrationResponse)
async def check_prior_auth(body: CheckPriorAuthRequest):
    """
    Schema-driven PA readiness check.

    Accepts chart text, payer identifier, and CPT code. Loads the compiled
    rule set for that payer/CPT, extracts structured patient data from the
    chart text, evaluates all policy rules, and returns a structured verdict.

    Args:
        body: JSON body with chart_text, payer, cpt_code.

    Returns:
        OrchestrationResponse with verdict, readiness_score, criteria, gaps,
        and next_steps.

    Raises:
        HTTPException 404: No compiled rules for payer/CPT.
        HTTPException 422: Evidence extraction failed.
        HTTPException 500: Rule evaluation or response-building failure.
    """
    try:
        # Step 1: Load compiled rules — 404 if not yet compiled
        compiled = _load_compiled_rules(body.payer.lower(), body.cpt_code)
        canonical_rules: list = compiled.get("canonical_rules", [])
        extraction_schema: dict = compiled.get("extraction_schema", {})
        logger.info(
            "Loaded %d rules and %d schema fields for %s/%s",
            len(canonical_rules),
            len(extraction_schema),
            body.payer,
            body.cpt_code,
        )

        # Step 2: Extract patient data (PHI path — BAA-covered provider required)
        try:
            patient_data = extract_evidence_schema_driven(
                body.chart_text, extraction_schema
            )
        except Exception as exc:
            logger.error("Evidence extraction failed: %s", exc)
            raise HTTPException(
                status_code=422,
                detail="Failed to extract clinical evidence from the chart.",
            )

        # Step 3: Evaluate rules deterministically — no LLM involved
        try:
            evaluation = evaluate_all(
                patient_data, canonical_rules, requested_cpt=body.cpt_code
            )
        except Exception as exc:
            logger.error("Rule evaluation failed: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Failed to evaluate patient evidence against policy rules.",
            )

        # Step 4: Build response
        excluded: bool = evaluation.get("excluded", False)
        results: list[dict] = evaluation["results"]
        total = len(results)
        met_count = sum(1 for r in results if r["met"])
        readiness_score = (
            0 if excluded else int((met_count / total * 100) if total > 0 else 0)
        )

        criteria: list[CriterionResult] = []
        gaps: list[str] = []
        fail_count = 0

        for result in results:
            met = result["met"]
            if not met:
                fail_count += 1
                gaps.append(result.get("gap_description", result["description"]))

            criteria.append(
                CriterionResult(
                    criterion=result["description"],
                    required=result.get("required_value", "Must be documented"),
                    found=result.get("patient_value", "Not found in chart"),
                    status="PASS" if met else "FAIL",
                )
            )

        verdict = _derive_verdict(readiness_score, fail_count, excluded)
        next_steps = _generate_next_steps(gaps, exception_applied=None)
        patient_name: str = patient_data.get("patient_name") or "Unknown Patient"

        return OrchestrationResponse(
            verdict=verdict,
            readiness_score=readiness_score,
            patient_name=patient_name,
            payer=PAYER_LABELS.get(body.payer.lower(), body.payer),
            cpt=body.cpt_code,
            procedure_label=CPT_LABELS.get(body.cpt_code, f"CPT {body.cpt_code}"),
            criteria=criteria,
            gaps=gaps,
            next_steps=next_steps,
            exception_applied=None,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in PA check: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during the PA check.",
        )
