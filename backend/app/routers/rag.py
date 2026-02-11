from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from app.middleware.auth import require_authentication, TokenData
from app.middleware.rate_limit import limiter
from typing import Optional

# from app.rag_pipeline.scripts.build_index_updated import build_index, INDEX_DIR
from app.rag_pipeline.scripts.extract_policy_rules import extract_policy_rules
from app.utils.save_json import save_analysis_to_json
from app.rag_pipeline.scripts.build_index_updated import  INDEX_DIR


router = APIRouter()
# THIS OUTPUTS MY POLICY CRITERIA CHECKLIST JSON

# ---------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------
class QueryRequest(BaseModel):
    query: str
    index_name: str | None = "default"


class QueryResponse(BaseModel):
    answer: str
    context: list[str]
    raw_output: str | None = None


class BuildIndexRequest(BaseModel):
    index_name: str | None = "default"


class BuildIndexResponse(BaseModel):
    message: str
    index_name: str


class PolicyRuleRequest(BaseModel):
    payer: str
    cpt_code: str
    index_name: str = "default"

class PolicyRuleResponse(BaseModel):
    rules: dict
    context: list[str]
    raw_output: str


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@router.post("/extract_policy_rules", response_model=PolicyRuleResponse)
@limiter.limit("200/hour")
def extract_policy_rules_endpoint(
    req: Request,
    request: PolicyRuleRequest,
    auth: tuple[Optional[TokenData], Optional[str]] = Depends(require_authentication)
):
    """
    Extract structured medical necessity rules from payer policy documents.

    **AUTHENTICATION REQUIRED**: This endpoint requires either:
    - Bearer token (JWT) in Authorization header
    - X-API-Key header with valid API key
    """
    
    result = extract_policy_rules(
        payer=request.payer,
        cpt_code=request.cpt_code,
        index_name=request.index_name
    )

    # result_dict = result.model_dump()
    # saved_path = save_analysis_to_json(result, output_dir=".")
    # print(f'Analysis succeeded and saved to {saved_path}!')

    return PolicyRuleResponse(**result)


# @router.post("/build_index", response_model=BuildIndexResponse)
# def api_build_index(req: BuildIndexRequest):
#     """Build a new RAG index."""
#     try:
#         # If your build_index() function needs the index name,
#         # modify it to accept a parameter. For now, we assume
#         # it builds into INDEX_DIR based on index_name.
#         build_index()
#         return BuildIndexResponse(
#             message="Index built successfully",
#             index_name=req.index_name
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete_index/{index_name}")
@limiter.limit("50/hour")
def delete_index(
    index_name: str,
    req: Request,
    auth: tuple[Optional[TokenData], Optional[str]] = Depends(require_authentication)
):
    """
    Delete an existing index by name.

    **AUTHENTICATION REQUIRED**: This endpoint requires either:
    - Bearer token (JWT) in Authorization header
    - X-API-Key header with valid API key
    """
    faiss_file = INDEX_DIR / f"{index_name}.faiss"
    meta_file = INDEX_DIR / f"{index_name}_meta.pkl"  # if you store metadata

    deleted = False

    if faiss_file.exists():
        faiss_file.unlink()
        deleted = True

    if meta_file.exists():
        meta_file.unlink()
        deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail="Index not found")

    return {"message": "Index deleted"}


@router.get("/list_indexes")
@limiter.limit("200/hour")
def list_indexes(
    req: Request,
    auth: tuple[Optional[TokenData], Optional[str]] = Depends(require_authentication)
):
    """
    List all available indexes.

    **AUTHENTICATION REQUIRED**: This endpoint requires either:
    - Bearer token (JWT) in Authorization header
    - X-API-Key header with valid API key
    """
    indexes = []

    for faiss_file in INDEX_DIR.glob("*.faiss"):
        name = faiss_file.stem  # removes .faiss
        indexes.append(name)

    return {"indexes": indexes}