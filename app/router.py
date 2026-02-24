"""
Single API endpoint: POST /api/compile

Accepts a policy document (PDF or TXT), payer ID, and CPT code.
Returns the compiled PolicyTemplate JSON and saves it to templates/.
"""

import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.reader import read_file
from app.schemas import PolicyTemplate
from app.services import compiler

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/compile", response_model=PolicyTemplate)
async def compile_policy(
    policy_file: UploadFile = File(..., description="Policy document (PDF or TXT)"),
    payer: str = Form(..., description="Payer identifier, e.g. 'utah_medicaid'"),
    cpt_code: str = Form(..., description="CPT code, e.g. '73721'"),
) -> PolicyTemplate:
    """
    Compile a payer policy document into a structured checklist JSON.

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
        result = compiler.compile(policy_text, payer, cpt_code)
    except Exception as exc:
        logger.exception("Compilation failed for payer=%s cpt=%s", payer, cpt_code)
        raise HTTPException(status_code=500, detail="Policy compilation failed.")

    return PolicyTemplate(**result)
