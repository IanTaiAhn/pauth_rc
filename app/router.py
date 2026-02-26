"""
Single API endpoint: POST /api/compile

Accepts a policy document (PDF or TXT), payer ID, and LCD code.
Returns the compiled PolicyTemplate JSON and saves it to templates/.
"""

import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from app.reader import read_file
from app.schemas import CompilationResponse, PolicyTemplate
from app.services import compiler

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/compile", response_model=CompilationResponse)
async def compile_policy(
    policy_file: UploadFile = File(..., description="Policy document (PDF or TXT)"),
    payer: str = Form(..., description="Payer identifier, e.g. 'medicare'"),
    lcd_code: str = Form(..., description="LCD code, e.g. 'L36007'"),
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
        result = compiler.compile(policy_text, payer, lcd_code, include_debug=include_debug)
    except Exception as exc:
        logger.exception("Compilation failed for payer=%s lcd=%s", payer, lcd_code)
        raise HTTPException(status_code=500, detail="Policy compilation failed.")

    # Result is now {"template": {...}, "debug": {...}} or just {"template": {...}}
    return CompilationResponse(**result)
