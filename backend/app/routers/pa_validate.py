from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import json
from datetime import datetime
from pathlib import Path

from backend.app.services.ingestion import extract_text
from backend.app.services.evidence import extract_evidence
from backend.app.services.readiness import compute_readiness
# THIS IS A BUNCH OF BOGUS RN, BUT I NEED TO FIGURE OUT HOW TO COMPARE THE JSON OBJECTS USING REAL RULES.

router = APIRouter()

# routers/rag.py - Add new endpoint
@router.post(
    "/validate_pa",
    summary="Validate PA request against policy criteria",
    tags=["PA Validation"]
)
async def validate_pa_endpoint(
    payer: str,
    cpt_code: str,
    patient_file: UploadFile,
    index_name: str = "default"
):
    """
    Validate a patient's PA request against payer policy criteria
    
    1. Extracts policy criteria from vector store
    2. Analyzes patient documentation
    3. Validates patient meets criteria
    4. Returns approval likelihood
    """
    try:
        # Step 1: Get policy criteria
        logger.info(f"Extracting policy for {payer} CPT {cpt_code}")
        policy_result = await run_in_threadpool(
            extract_policy_rules,
            payer=payer,
            cpt_code=cpt_code,
            index_name=index_name
        )
        
        # Step 2: Analyze patient documentation
        logger.info("Analyzing patient documentation")
        # TODO: Integrate your patient document analyzer here
        # patient_analysis = analyze_patient_document(patient_file)
        
        # For now, use your example data
        patient_analysis = {
            "timestamp": datetime.now().isoformat(),
            "analysis": {
                "filename": patient_file.filename,
                "score": 100,
                "requirements": {
                    "symptom_duration_months": 4,
                    "conservative_therapy": {
                        "physical_therapy": {
                            "attempted": True,
                            "duration_weeks": 12
                        },
                        "nsaids": {
                            "documented": True,
                            "outcome": "failed"
                        }
                    },
                    "imaging": {
                        "documented": True,
                        "type": "X-ray",
                        "body_part": "Right Knee",
                        "months_ago": 1
                    },
                    "functional_impairment": {
                        "documented": True,
                        "description": "significant functional limitations"
                    },
                    "evidence_notes": [
                        "Patient has completed 8 weeks of conservative management",
                        "Physical therapy: 2x weekly",
                        "Total sessions: 12 sessions completed"
                    ]
                }
            }
        }
        
        # Step 3: Validate
        logger.info("Validating PA request")
        validation_results = validate_pa_request(
            policy_rules=policy_result["rules"],
            patient_data=patient_analysis
        )
        
        return {
            "success": True,
            "validation": validation_results,
            "policy_used": {
                "payer": payer,
                "cpt_code": cpt_code,
                "source_documents": len(policy_result.get("context", []))
            },
            "patient_analysis": patient_analysis["analysis"]
        }
        
    except Exception as e:
        logger.error(f"PA validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
# Try testing with this data here or the data we made?
# # test_validation.py
# import json
# from validation.pa_validator import validate_pa_request

# # Your policy from RAG
# policy = {
#     "payer": "Aetna",
#     "cpt_code": "73721",
#     "coverage_criteria": {
#         "clinical_indications": [
#             "Suspected meniscal tear (ICD-10: M23.2xx, M23.3xx)",
#             # ... rest
#         ],
#         "prerequisites": [
#             "Weight-bearing X-rays within 60 days"
#         ]
#     }
# }

# # Your patient data
# patient = {
#     "analysis": {
#         "requirements": {
#             "symptom_duration_months": 4,
#             "conservative_therapy": {
#                 "physical_therapy": {
#                     "attempted": True,
#                     "duration_weeks": 12
#                 },
#                 "nsaids": {
#                     "documented": True
#                 }
#             },
#             "imaging": {
#                 "documented": True,
#                 "months_ago": 1
#             }
#         }
#     }
# }

# # Validate
# results = validate_pa_request(policy, patient)
# print(results["report"])