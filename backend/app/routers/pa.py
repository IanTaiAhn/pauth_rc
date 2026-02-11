from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from app.services.ingestion import extract_text
from app.services.evidence import extract_evidence, extract_evidence_multi
from app.services.readiness import compute_readiness
from app.utils.save_json import save_analysis_to_json
from app.api_models.schemas import InitialPatientExtraction, MultiChartPatientExtraction
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


@router.post("/extract_patient_chart_multi", response_model=MultiChartPatientExtraction)
async def analyze_pa_multi(files: List[UploadFile] = File(...)):
    """
    Analyze multiple prior authorization documents for the same patient.
    Accepts multiple PDF, DOCX, or TXT files and merges evidence into a single assessment.

    This endpoint handles real clinical workflows where a patient may have:
    - Multiple visit notes from different dates
    - Follow-up appointments with updated information
    - Different providers documenting treatments

    The system will:
    1. Extract evidence from each chart independently
    2. Merge the results using intelligent aggregation:
       - Conservative therapy: ANY documented attempt = documented
       - Duration values: Use MAXIMUM across all charts
       - Evidence notes: Accumulate ALL unique notes
       - Most recent data wins for conflicting values

    Returns:
        - filenames: List of uploaded file names
        - score: Combined readiness score for the PA
        - requirements: Merged evidence from all documents
        - missing_items: List of missing required items
        - source_metadata: Details about which files contributed which data
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="No files provided. Please upload at least one file."
        )

    try:
        chart_texts = []
        filenames = []

        # Extract text from all uploaded files
        for file in files:
            contents = await file.read()
            text = extract_text(contents)

            if not text or len(text.strip()) < 10:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' is empty or too short to process"
                )

            chart_texts.append((text, file.filename))
            filenames.append(file.filename)
            await file.close()

        print(f'Extracted text from {len(filenames)} files successfully...')
        print(f'Files: {", ".join(filenames)}')

        # Process multiple documents and merge evidence
        print('Processing multiple charts (this may take a while)...')
        evidence = extract_evidence_multi(chart_texts, use_groq=True)

        if not evidence:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract evidence from the provided charts"
            )

        print('Evidence extracted and merged...')

        # Compute readiness score from merged evidence
        score, missing = compute_readiness(evidence)
        print(f'Computed combined readiness score: {score}')

        # Extract source metadata if present
        source_metadata = evidence.pop("_multi_source_metadata", None)

        # Create response object
        response = MultiChartPatientExtraction(
            filenames=filenames,
            score=score,
            requirements=evidence,
            missing_items=missing,
            source_metadata=source_metadata
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing files: {str(e)}"
        )