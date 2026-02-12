"""
Orchestration endpoint for single-call PA readiness check.

Consolidates the entire PA pipeline into one API call:
1. Ingest patient chart file
2. Extract clinical evidence via LLM
3. Retrieve relevant policy rules via RAG
4. Normalize patient and policy data
5. Evaluate evidence against rules
6. Return structured response with verdict, score, criteria, and gaps
"""

import logging
from typing import Literal
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.services.ingestion import extract_text
from app.services.evidence import extract_evidence
from app.rag_pipeline.scripts.extract_policy_rules import extract_policy_rules
from app.normalization.normalized_custom import (
    normalize_patient_evidence,
    normalize_policy_criteria,
)
from app.rules.rule_engine import evaluate_all
from app.api_models.schemas import OrchestrationResponse, CriterionResult

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Map (payer, cpt) to FAISS index names
INDEX_MAP = {
    ("utah_medicaid", "73721"): "utah_medicaid_73721",
    ("utah_medicaid", "73722"): "utah_medicaid_73722",
    ("utah_medicaid", "73723"): "utah_medicaid_73723",
    ("aetna", "73721"): "aetna_73721",
    ("aetna", "73722"): "aetna_73722",
    ("aetna", "73723"): "aetna_73723",
}

# CPT code labels for human-readable display
CPT_LABELS = {
    "73721": "MRI Knee Without Contrast",
    "73722": "MRI Knee With Contrast",
    "73723": "MRI Knee Without and With Contrast",
}

# Payer display names
PAYER_LABELS = {
    "utah_medicaid": "Utah Medicaid",
    "aetna": "Aetna",
}


def resolve_index(payer: str, cpt: str) -> str:
    """
    Resolve (payer, cpt) to FAISS index name.

    Args:
        payer: Payer identifier (e.g., "utah_medicaid", "aetna")
        cpt: CPT code string (e.g., "73721")

    Returns:
        Index name string

    Raises:
        HTTPException: If no index exists for the combination
    """
    key = (payer.lower(), cpt)
    if key not in INDEX_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"No policy index found for payer '{payer}' and CPT code '{cpt}'. "
                   f"Supported combinations: {list(INDEX_MAP.keys())}"
        )
    return INDEX_MAP[key]


def derive_verdict(
    readiness_score: float,
    fail_count: int
) -> Literal["LIKELY_TO_APPROVE", "LIKELY_TO_DENY", "NEEDS_REVIEW"]:
    """
    Derive PA verdict from readiness score and failure count.

    Logic:
    - Score >= 80 and no failures → LIKELY_TO_APPROVE
    - Score < 50 or 2+ failures → LIKELY_TO_DENY
    - Everything else → NEEDS_REVIEW
    """
    if readiness_score >= 80 and fail_count == 0:
        return "LIKELY_TO_APPROVE"
    elif readiness_score < 50 or fail_count >= 2:
        return "LIKELY_TO_DENY"
    else:
        return "NEEDS_REVIEW"


def generate_next_steps(gaps: list[str], exception_applied: str | None) -> str:
    """
    Generate plain-English next steps guidance based on gaps.

    Args:
        gaps: List of gap descriptions
        exception_applied: Exception pathway name if any

    Returns:
        Human-readable next steps string
    """
    gap_count = len(gaps)

    if gap_count == 0:
        base = "All criteria met. This chart is ready for PA submission."
    elif gap_count == 1:
        base = "One criterion is unmet. Resolve the item in the gaps list before submitting."
    else:
        base = "Multiple criteria are unmet. Review the gaps list and update the chart before submitting."

    if exception_applied:
        base += f" Note: Exception pathway applied — {exception_applied}."

    return base


def extract_patient_name(patient_json: dict) -> str:
    """
    Extract patient name from the raw patient chart JSON.

    Tries multiple paths with fallback to "Unknown Patient".
    """
    # Try direct name field
    if "name" in patient_json:
        return patient_json["name"]

    # Try nested in requirements
    if "requirements" in patient_json:
        reqs = patient_json["requirements"]
        if isinstance(reqs, dict) and "name" in reqs:
            return reqs["name"]

    # Fallback
    return "Unknown Patient"


@router.post("/check_prior_auth", response_model=OrchestrationResponse)
async def check_prior_auth(
    file: UploadFile = File(..., description="Patient chart file (PDF or TXT)"),
    payer: str = Form(..., description="Payer identifier (e.g., 'utah_medicaid', 'aetna')"),
    cpt: str = Form(..., description="CPT code (e.g., '73721', '73722', '73723')"),
):
    """
    Single-call PA readiness check endpoint.

    Accepts a patient chart file, payer identifier, and CPT code.
    Runs the full PA pipeline internally and returns a structured
    response with verdict, score, criteria results, and actionable gaps.

    Args:
        file: Patient chart file (PDF or TXT)
        payer: Payer identifier (e.g., "utah_medicaid", "aetna")
        cpt: CPT code string (e.g., "73721", "73722", "73723")

    Returns:
        OrchestrationResponse with verdict, score, criteria, gaps, and next steps

    Raises:
        HTTPException 400: Unsupported payer/CPT combination
        HTTPException 422: File parsing or extraction failure
        HTTPException 500: Internal pipeline error
    """
    try:
        logger.info(f"Starting PA check for payer={payer}, cpt={cpt}, file={file.filename}")

        # Step 1: Ingest file
        try:
            file_contents = await file.read()
            text = extract_text(file_contents)
            if not text:
                raise HTTPException(
                    status_code=422,
                    detail="Could not extract text from the uploaded file. Please ensure it's a valid PDF or TXT."
                )
            logger.info(f"Extracted {len(text)} characters from {file.filename}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"File ingestion failed: {e}")
            raise HTTPException(
                status_code=422,
                detail="Failed to read or parse the uploaded file."
            )

        # Step 2: Extract patient chart evidence
        try:
            patient_json = extract_evidence(text, use_groq=True)
            logger.info("Patient evidence extracted via LLM")
        except Exception as e:
            logger.error(f"Patient chart extraction failed: {e}")
            raise HTTPException(
                status_code=422,
                detail="Failed to extract clinical evidence from the chart."
            )

        # Step 3: Resolve index and extract policy rules
        try:
            index_name = resolve_index(payer, cpt)
            logger.info(f"Resolved index: {index_name}")
        except HTTPException:
            raise

        try:
            policy_result = extract_policy_rules(payer, cpt, index_name=index_name)
            policy_json = policy_result.get("rules", {})
            if not policy_json or "error" in policy_json:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve policy rules for this payer and CPT code."
                )
            logger.info(f"Policy rules extracted via RAG for {index_name}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Policy extraction failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve policy rules."
            )

        # Step 4: Normalize patient evidence
        try:
            normalized_patient = normalize_patient_evidence(patient_json)
            logger.info("Patient evidence normalized")
        except Exception as e:
            logger.error(f"Patient normalization failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to normalize patient evidence."
            )

        # Step 5: Normalize policy rules
        try:
            normalized_policy = normalize_policy_criteria(policy_json)
            logger.info(f"Policy rules normalized: {len(normalized_policy)} rules")
        except Exception as e:
            logger.error(f"Policy normalization failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to normalize policy rules."
            )

        # Step 6: Evaluate rules
        try:
            evaluation = evaluate_all(normalized_patient, normalized_policy)
            logger.info(f"Rule evaluation complete: {evaluation['rules_met']}/{evaluation['total_rules']} met")
        except Exception as e:
            logger.error(f"Rule evaluation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to evaluate patient evidence against policy rules."
            )

        # Step 7: Build response
        try:
            # Extract patient name
            patient_name = extract_patient_name(patient_json)

            # Compute readiness score
            total_rules = evaluation["total_rules"]
            rules_met = evaluation["rules_met"]
            readiness_score = int((rules_met / total_rules * 100) if total_rules > 0 else 0)

            # Build criteria list
            criteria = []
            fail_count = 0
            gaps = []

            for result in evaluation["results"]:
                status = "PASS" if result["met"] else "FAIL"
                if not result["met"]:
                    fail_count += 1
                    # Extract gap description from rule
                    gap_desc = result.get("gap_description", result["description"])
                    gaps.append(gap_desc)

                criteria.append(CriterionResult(
                    criterion=result["description"],
                    required=result.get("required_value", "Must be documented"),
                    found=result.get("patient_value", "Not found in chart"),
                    status=status,
                ))

            # Derive verdict
            verdict = derive_verdict(readiness_score, fail_count)

            # TODO: Implement exception pathway detection
            # For now, this is a placeholder
            exception_applied = None

            # Generate next steps
            next_steps = generate_next_steps(gaps, exception_applied)

            # Get display labels
            payer_label = PAYER_LABELS.get(payer.lower(), payer)
            procedure_label = CPT_LABELS.get(cpt, f"CPT {cpt}")

            response = OrchestrationResponse(
                verdict=verdict,
                readiness_score=readiness_score,
                patient_name=patient_name,
                payer=payer_label,
                cpt=cpt,
                procedure_label=procedure_label,
                criteria=criteria,
                gaps=gaps,
                next_steps=next_steps,
                exception_applied=exception_applied,
            )

            logger.info(f"PA check complete: verdict={verdict}, score={readiness_score}")
            return response

        except Exception as e:
            logger.error(f"Response building failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to build response."
            )

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        # Log full traceback server-side but return generic message to client
        logger.exception(f"Unexpected error in PA check pipeline: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during the PA check."
        )
    finally:
        # Clean up
        await file.close()
