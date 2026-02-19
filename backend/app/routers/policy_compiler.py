"""
Policy Compiler router — index-build time (no PHI).

Provides an HTTP interface to compile a payer policy document into a
structured rule set and save it to compiled_rules/{payer}_{cpt_code}.json.

This endpoint never receives patient data and has no PHI. Groq is used
as the LLM provider by default.
"""

import io

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.rag_pipeline.scripts.compile_policy import compile_policy

router = APIRouter()


# ---------------------------------------------------------
# Response model
# ---------------------------------------------------------

class CompilePolicyResponse(BaseModel):
    payer: str
    cpt_code: str
    rule_count: int
    schema_field_count: int
    validation_errors: list[str]
    model: str


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _extract_text(filename: str, file_bytes: bytes) -> str:
    """Extract plain text from an uploaded TXT or PDF file."""
    if filename.lower().endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return file_bytes.decode("utf-8")


# ---------------------------------------------------------
# Endpoint
# ---------------------------------------------------------

@router.post("/compile_policy", response_model=CompilePolicyResponse)
async def compile_policy_endpoint(
    policy_file: UploadFile = File(..., description="Policy document (PDF or TXT)"),
    payer: str = Form(..., description="Payer identifier (e.g., 'utah_medicaid')"),
    cpt_code: str = Form(..., description="CPT code (e.g., '73721')"),
) -> CompilePolicyResponse:
    """
    Compile a payer policy document into canonical rules and an extraction
    schema, then save the result to compiled_rules/{payer}_{cpt_code}.json.

    This is an index-build-time operation. It does NOT accept patient data
    and involves no PHI. Groq is used as the LLM provider.

    Accepts a file upload (PDF or TXT) rather than raw text in the request
    body, which avoids JSON encoding issues with large documents.

    Returns a summary of the compilation result. The full compiled output is
    written to disk and also available via GET /api/list_compiled_rules.
    """
    try:
        file_bytes = await policy_file.read()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Failed to read uploaded file.") from exc
    finally:
        await policy_file.close()

    try:
        policy_text = _extract_text(policy_file.filename or "", file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract text from file: {exc}",
        ) from exc

    if not policy_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Uploaded file contains no extractable text.",
        )

    try:
        result = compile_policy(
            policy_text=policy_text,
            payer=payer,
            cpt_code=cpt_code,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return CompilePolicyResponse(
        payer=result["_payer"],
        cpt_code=result["_cpt_code"],
        rule_count=len(result.get("canonical_rules", [])),
        schema_field_count=len(result.get("extraction_schema", {})),
        validation_errors=result.get("_validation_errors", []),
        model=result.get("_model", ""),
    )
