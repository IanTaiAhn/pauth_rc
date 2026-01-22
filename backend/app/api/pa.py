from fastapi import APIRouter, UploadFile
from app.services.ingestion import extract_text
from app.services.evidence import extract_evidence
from app.services.readiness import compute_readiness
from app.services.justification import build_justification

router = APIRouter()

@router.post("/analyze")
async def analyze_pa(file: UploadFile):
    text = extract_text(await file.read())
    evidence = extract_evidence(text)
    score, missing = compute_readiness(evidence)
    justification = build_justification(evidence)

    return {
        "score": score,
        "requirements": evidence,
        "missing_items": missing,
        "justification_text": justification
    }

# chat gpt helped
# @router.post("/analyze")
# def check_pa(request: PARequest):
#     text = ingest_document(request.text)
#     evidence = extract_evidence(text)
#     criteria = get_policy_criteria(request.payer, request.cpt)
#     readiness = compute_readiness(evidence, criteria)
#     justification = generate_justification(
#         evidence, criteria, criteria["raw_policy_text"]
#     )

#     return {
#         "evidence": evidence,
#         "readiness": readiness,
#         "justification": justification
#     }