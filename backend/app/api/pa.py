from fastapi import FastAPI, UploadFile, File, HTTPException
from app.services.ingestion import extract_text
from app.services.evidence import extract_evidence
from app.services.readiness import compute_readiness
# from app.services.justification import build_justification

app = FastAPI(title="PA RC MVP")

@app.post("/analyze")
async def analyze_pa(file: UploadFile = File(...)):
    """
    Analyze a prior authorization document.
    Accepts PDF, DOCX, or TXT files.
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

        # Compliant langague for a clinical setting using the evidence found, and the actual criteria_chunks.
        # justification = build_justification(evidence, criteria_chunks)
        # print('justifying...')

        print('succeeded!')
        return {
            "filename": file.filename,
            "score": score,
            "requirements": evidence,
            "missing_items": missing,
            # "justification_text": justification
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    
    finally:
        # Clean up - close the file
        await file.close()

@app.get("/")
async def root():
    return {"message": "Local RAG API is running"}