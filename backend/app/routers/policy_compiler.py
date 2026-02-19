"""
Policy Compiler router — index-build time (no PHI).

Provides an HTTP interface to compile a payer policy document into a
structured rule set and save it to compiled_rules/{payer}_{cpt_code}.json.

This endpoint never receives patient data and has no PHI. Groq is used
as the LLM provider by default.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.rag_pipeline.scripts.compile_policy import compile_policy

router = APIRouter()


# ---------------------------------------------------------
# Request / response models
# ---------------------------------------------------------

class CompilePolicyRequest(BaseModel):
    policy_text: str
    payer: str
    cpt_code: str


class CompilePolicyResponse(BaseModel):
    payer: str
    cpt_code: str
    rule_count: int
    schema_field_count: int
    validation_errors: list[str]
    model: str


# ---------------------------------------------------------
# Endpoint
# ---------------------------------------------------------

@router.post("/compile_policy", response_model=CompilePolicyResponse)
def compile_policy_endpoint(request: CompilePolicyRequest) -> CompilePolicyResponse:
    """
    Compile a payer policy document into canonical rules and an extraction
    schema, then save the result to compiled_rules/{payer}_{cpt_code}.json.

    This is an index-build-time operation. It does NOT accept patient data
    and involves no PHI. Groq is used as the LLM provider.

    Returns a summary of the compilation result. The full compiled output is
    written to disk and also available via GET /api/list_compiled_rules.
    """
    try:
        result = compile_policy(
            policy_text=request.policy_text,
            payer=request.payer,
            cpt_code=request.cpt_code,
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
