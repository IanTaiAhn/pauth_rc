from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from app.middleware.auth import require_authentication, TokenData
from app.middleware.rate_limit import limiter
from typing import Optional

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
@limiter.limit("100/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    auth: tuple[Optional[TokenData], Optional[str]] = Depends(require_authentication)
):
    """
    Upload a document (PDF or TXT) to the server.

    **AUTHENTICATION REQUIRED**: This endpoint requires either:
    - Bearer token (JWT) in Authorization header
    - X-API-Key header with valid API key
    """
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
@limiter.limit("200/hour")
def list_uploaded_docs(
    request: Request,
    auth: tuple[Optional[TokenData], Optional[str]] = Depends(require_authentication)
):
    """
    List all uploaded documents.

    **AUTHENTICATION REQUIRED**: This endpoint requires either:
    - Bearer token (JWT) in Authorization header
    - X-API-Key header with valid API key
    """
    files = [f.name for f in UPLOAD_DIR.glob("*") if f.is_file()]
    return {"files": files}


@router.delete("/delete_uploaded_doc/{filename}")
@limiter.limit("100/hour")
def delete_uploaded_doc(
    filename: str,
    request: Request,
    auth: tuple[Optional[TokenData], Optional[str]] = Depends(require_authentication)
):
    """
    Delete an uploaded document by filename.

    **AUTHENTICATION REQUIRED**: This endpoint requires either:
    - Bearer token (JWT) in Authorization header
    - X-API-Key header with valid API key
    """
    file_path = UPLOAD_DIR / filename
    
    if file_path.exists():
        file_path.unlink()
        return {"message": "File deleted"}
    else:
        raise HTTPException(status_code=404, detail="File not found")