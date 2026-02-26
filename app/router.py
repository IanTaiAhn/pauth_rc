"""
API endpoints for policy compilation pipeline.

POST /api/compile  — full two-step pipeline (structure + detail) → saves template
POST /api/structure — Step 1 only (structure skeleton), with optional save
"""

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from app.reader import read_file
from app.schemas import CompilationResponse, PolicyTemplate, SkeletonResponse
from app.services import compiler
from app.services import structurer

_TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "./templates"))

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/compile", response_model=CompilationResponse)
async def compile_policy(
    policy_file: UploadFile = File(..., description="Policy document (PDF or TXT)"),
    payer: str = Form(..., description="Payer identifier, e.g. 'utah_medicaid'"),
    cpt_code: str = Form(..., description="CPT code, e.g. '73721'"),
    include_debug: bool = Query(False, description="Include prompts and raw LLM responses in the response"),
) -> CompilationResponse:
    """
    Compile a payer policy document into a structured checklist JSON.

    No patient data. No PHI. Template-creation only.

    Set include_debug=true to receive prompts and raw LLM responses for both pipeline steps.
    """
    try:
        file_bytes = await policy_file.read()
    except Exception:
        raise HTTPException(status_code=422, detail="Failed to read uploaded file.")
    finally:
        await policy_file.close()

    try:
        policy_text = read_file(policy_file.filename or "", file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to extract text: {exc}")

    if not policy_text.strip():
        raise HTTPException(status_code=422, detail="Uploaded file contains no extractable text.")

    try:
        result = compiler.compile(policy_text, payer, cpt_code, include_debug=include_debug)
    except Exception as exc:
        logger.exception("Compilation failed for payer=%s cpt=%s", payer, cpt_code)
        raise HTTPException(status_code=500, detail="Policy compilation failed.")

    # Result is now {"template": {...}, "debug": {...}} or just {"template": {...}}
    return CompilationResponse(**result)


@router.post("/structure", response_model=SkeletonResponse)
async def structure_policy(
    policy_file: UploadFile = File(..., description="Policy document (PDF or TXT)"),
    payer: str = Form(..., description="Payer identifier, e.g. 'utah_medicaid'"),
    cpt_code: str = Form(..., description="CPT code, e.g. '73721'"),
    save: bool = Query(False, description="Save the skeleton JSON to templates/{payer}_{cpt_code}_skeleton.json"),
) -> SkeletonResponse:
    """
    Run Step 1 only: extract the policy structure skeleton from a payer policy document.

    Returns the raw skeleton with sections, requirement types, exception pathways,
    and exclusions — no detail fields filled in yet.

    Set save=true to persist the skeleton to templates/{payer}_{cpt_code}_skeleton.json.

    No patient data. No PHI. Template-creation only.
    """
    try:
        file_bytes = await policy_file.read()
    except Exception:
        raise HTTPException(status_code=422, detail="Failed to read uploaded file.")
    finally:
        await policy_file.close()

    try:
        policy_text = read_file(policy_file.filename or "", file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to extract text: {exc}")

    if not policy_text.strip():
        raise HTTPException(status_code=422, detail="Uploaded file contains no extractable text.")

    try:
        skeleton = structurer.create_skeleton(policy_text, payer, cpt_code)
    except Exception as exc:
        logger.exception("Structuring failed for payer=%s cpt=%s", payer, cpt_code)
        raise HTTPException(status_code=500, detail="Policy structuring failed.")

    saved = False
    if save:
        try:
            _TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            output_path = _TEMPLATES_DIR / f"{payer}_{cpt_code}_skeleton.json"
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(skeleton, fh, indent=2, ensure_ascii=False)
            logger.info("Saved skeleton to %s", output_path)
            saved = True
        except Exception:
            logger.exception("Failed to save skeleton for payer=%s cpt=%s", payer, cpt_code)

    return SkeletonResponse(
        payer=skeleton.get("payer", payer),
        cpt_code=skeleton.get("cpt_code", cpt_code),
        checklist_sections=skeleton.get("checklist_sections", []),
        exception_pathways=skeleton.get("exception_pathways", []),
        exclusions=skeleton.get("exclusions", []),
        saved=saved,
    )
