from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.ingestion import extract_text
from app.services.evidence import extract_evidence
from app.services.readiness import compute_readiness
from app.utils.save_json import save_analysis_to_json
from app.api_models.schemas import InitialPatientExtraction
# from app.services.justification import build_justification
# THIS OUTPUTS MY PATIENT CHART JSON
# TODO make this strictly a patient chart extracter. Since this will be working with HIPPA, I probably will need to rework this.

router = APIRouter()


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@router.post("/extract_patient_chart", response_model=InitialPatientExtraction)
async def analyze_pa(file: UploadFile = File(...)):
    """
    Analyze a prior authorization document.
    Accepts PDF, DOCX, or TXT files.
    
    Returns:
        - filename: Name of the uploaded file
        - score: Readiness score for the PA
        - requirements: Extracted evidence from the document
        - missing_items: List of missing required items
    """
    try:
        # Read file contents
        contents = await file.read()
        
        # Extract text from the uploaded file
        text = extract_text(contents)
        print('extracted successful...')
        # print('text: ', text)

        print('long wait begins...')
        # Process the document
        evidence = extract_evidence(text, use_groq=True)
        print('evidence extracted...')


        score, missing = compute_readiness(evidence)
        print('computed score...')

        # Create response object
        response = InitialPatientExtraction(
            filename=file.filename,
            score=score,
            requirements=evidence,
            missing_items=missing,
        )
        
        # Save to JSON file in the root directory
        # Convert Pydantic model to dict for JSON serialization
        # response_dict = response.model_dump()
        # saved_path = save_analysis_to_json(response_dict, output_dir=".")
        
        # print(f'Analysis succeeded and saved to {saved_path}!')
        
        return response
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing file: {str(e)}"
        )
    
    finally:
        # Clean up - close the file
        await file.close()