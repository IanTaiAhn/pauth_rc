"""
Prior Authorization — schema-driven patient chart extraction endpoint.

POST /api/extract_patient_chart

Follows Phase 2 (Schema-Driven Patient Extraction) from docs/architecture_guide.md:
  1. Ingest the uploaded chart file → plain text.
  2. Load the compiled rule set for the requested payer/CPT combination.
  3. Extract patient fields from the chart using the compiled extraction_schema.
  4. Return the extracted field values for downstream rule evaluation.

PHI boundary: chart text contains PHI. extract_evidence_schema_driven() enforces
provider="bedrock" and will raise ValueError for any other provider.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api_models.schemas import SchemaExtractionResponse
from app.services.evidence import get_extractor
from app.services.ingestion import extract_text

logger = logging.getLogger(__name__)

router = APIRouter()

# Compiled rule sets are stored here by compile_policy.py
COMPILED_RULES_DIR = (
    Path(__file__).resolve().parent.parent / "rag_pipeline" / "compiled_rules"
)


def _load_compiled_rules(payer: str, cpt_code: str) -> dict | None:
    """Load a compiled rule set from disk. Returns None if not found."""
    path = COMPILED_RULES_DIR / f"{payer}_{cpt_code}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.post("/extract_patient_chart", response_model=SchemaExtractionResponse)
async def extract_patient_chart(
    file: UploadFile = File(...),
    payer: str = Form(...),
    cpt_code: str = Form(...),
):
    """
    Extract structured patient evidence from a chart using schema-driven extraction.

    Loads the compiled extraction schema for the given payer/CPT combination
    and uses it to drive PHI extraction via AWS Bedrock (BAA-covered).

    Args:
        file:     Patient chart PDF or TXT file (contains PHI).
        payer:    Payer identifier matching a compiled rule set (e.g. "utah_medicaid").
        cpt_code: CPT code matching a compiled rule set (e.g. "73721").

    Returns:
        Extracted patient field values keyed by schema field name.
    """
    try:
        contents = await file.read()
        text = extract_text(contents)

        # Load compiled rules for this payer/CPT pair
        compiled = _load_compiled_rules(payer, cpt_code)
        if compiled is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No compiled rules found for payer='{payer}', cpt_code='{cpt_code}'. "
                    "Run compile_policy() first via POST /api/compile_policy."
                ),
            )

        extraction_schema = compiled.get("extraction_schema")
        if not extraction_schema:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Compiled rules for {payer}/{cpt_code} contain no extraction_schema. "
                    "Re-run compile_policy() to regenerate the rule set."
                ),
            )

        # Schema-driven PHI extraction — Bedrock is enforced inside this method
        extractor = get_extractor(use_groq=True)
        patient_data = extractor.extract_evidence_schema_driven(
            chart_text=text,
            extraction_schema=extraction_schema,
            provider="bedrock",
        )

        return SchemaExtractionResponse(
            filename=file.filename,
            payer=payer,
            cpt_code=cpt_code,
            patient_data=patient_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Schema-driven extraction failed: %s", e)
        raise HTTPException(status_code=500, detail="Error processing chart file.")

    finally:
        await file.close()
