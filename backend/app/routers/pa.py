from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import json
from datetime import datetime
from pathlib import Path

from backend.app.services.ingestion import extract_text
from backend.app.services.evidence import extract_evidence
from backend.app.services.readiness import compute_readiness
# from app.services.justification import build_justification

router = APIRouter()


# ---------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------
class AnalysisResponse(BaseModel):
    filename: str
    score: float | int
    requirements: dict
    missing_items: list[str]
    # justification_text: str | None = None


# ---------------------------------------------------------
# Helper function to save JSON
# ---------------------------------------------------------
def save_analysis_to_json(response_data: dict, output_dir: str = "."):
    """
    Save the analysis response to a JSON file in the specified directory.
    
    Args:
        response_data: Dictionary containing the analysis results
        output_dir: Directory where to save the file (default: current directory/root)
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_filename = response_data.get('filename', 'unknown')
    # Remove file extension and sanitize
    base_name = Path(original_filename).stem
    json_filename = f"analysis_{base_name}_{timestamp}.json"
    
    # Full path to save
    json_path = output_path / json_filename
    
    # Add metadata
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "analysis": response_data
    }
    
    # Save to JSON file
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Analysis saved to: {json_path}")
    return str(json_path)


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@router.post("/analyze", response_model=AnalysisResponse)
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
        evidence = extract_evidence(text)
        print('evidence extracted...')
        # print('evidence as json:', evidence)

        # TODO add RAG here for the payer policy criteria.
        # Example....
        # STEP 2 — Policy retrieval (RAG)
        # criteria = get_policy_criteria(
        #     payer="BCBS",        # later from UI
        #     cpt_code="62323"     # later extracted or selected
        # )

        score, missing = compute_readiness(evidence)
        print('computed score...')

        # Compliant language for a clinical setting using the evidence found, 
        # and the actual criteria_chunks.
        # justification = build_justification(evidence, criteria_chunks)
        # print('justifying...')

        # Create response object
        response = AnalysisResponse(
            filename=file.filename,
            score=score,
            requirements=evidence,
            missing_items=missing,
            # justification_text=justification
        )
        
        # Save to JSON file in the root directory
        # Convert Pydantic model to dict for JSON serialization
        response_dict = response.model_dump()
        saved_path = save_analysis_to_json(response_dict, output_dir=".")
        
        print(f'Analysis succeeded and saved to {saved_path}!')
        
        return response
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing file: {str(e)}"
        )
    
    finally:
        # Clean up - close the file
        await file.close()