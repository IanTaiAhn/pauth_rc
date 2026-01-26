from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter()

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
UPLOAD_DIR = Path("uploaded_docs")
UPLOAD_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@router.post("/upload_document")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document (PDF or TXT) to the server."""
    if file.content_type not in ["application/pdf", "text/plain"]:
        raise HTTPException(
            status_code=400, 
            detail="Only PDF or TXT files allowed"
        )

    file_path = UPLOAD_DIR / file.filename

    # Save file
    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {
        "message": "File uploaded successfully", 
        "filename": file.filename
    }


@router.get("/list_uploaded_docs")
def list_uploaded_docs():
    """List all uploaded documents."""
    files = [f.name for f in UPLOAD_DIR.glob("*") if f.is_file()]
    return {"files": files}


@router.delete("/delete_uploaded_doc/{filename}")
def delete_uploaded_doc(filename: str):
    """Delete an uploaded document by filename."""
    file_path = UPLOAD_DIR / filename
    
    if file_path.exists():
        file_path.unlink()
        return {"message": "File deleted"}
    else:
        raise HTTPException(status_code=404, detail="File not found")