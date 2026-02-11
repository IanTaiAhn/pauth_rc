from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.rag_pipeline.scripts.build_index_updated import build_index, INDEX_DIR
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
def extract_policy_rules_endpoint(request: PolicyRuleRequest):
    """Extract structured medical necessity rules from payer policy documents."""
    
    result = extract_policy_rules(
        payer=request.payer,
        cpt_code=request.cpt_code,
        index_name=request.index_name
    )

    # result_dict = result.model_dump()
    # saved_path = save_analysis_to_json(result, output_dir=".")
    # print(f'Analysis succeeded and saved to {saved_path}!')

    return PolicyRuleResponse(**result)


@router.post("/build_index", response_model=BuildIndexResponse)
def api_build_index(req: BuildIndexRequest):
    """Build a new RAG index."""
    try:
        # If your build_index() function needs the index name,
        # modify it to accept a parameter. For now, we assume
        # it builds into INDEX_DIR based on index_name.
        build_index()
        return BuildIndexResponse(
            message="Index built successfully",
            index_name=req.index_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete_index/{index_name}")
def delete_index(index_name: str):
    """Delete an existing index by name."""
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
def list_indexes():
    """List all available indexes."""
    indexes = []

    for faiss_file in INDEX_DIR.glob("*.faiss"):
        name = faiss_file.stem  # removes .faiss
        indexes.append(name)

    return {"indexes": indexes}