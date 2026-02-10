# Why it exists

# You don’t want to retrofit:
# auth
# request validation
# basic audit hooks

# MVP version (very thin)
# app/core/security.py
from fastapi import HTTPException

def validate_upload(content_type: str, size_bytes: int):
    if content_type not in {"application/pdf", "text/plain"}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if size_bytes > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

# You’re not building OAuth yet.
# You’re just preventing obvious abuse.