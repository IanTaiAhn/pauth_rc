import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.routers import rag, documents, pa, authz, normalization
from app.middleware.rate_limit import limiter

app = FastAPI(title="P-Auth RC")

# ---------------------------------------------------------
# Rate Limiting Setup
# ---------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------
# CORS Configuration (Environment-Driven)
# ---------------------------------------------------------
# Get allowed origins from environment variable
# Format: comma-separated list of origins
# Example: "http://localhost:5173,https://app.example.com"
ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173"  # Default for development
).split(",")

# Strip whitespace from origins
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

# Allow credentials only if explicitly enabled
ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"

# CORS MUST BE ADDED BEFORE ROUTES
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rag.router, prefix="/api", tags=["RAG"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(pa.router, prefix="/api", tags=["Prior Authorization"])
app.include_router(authz.router, prefix="/api", tags=["Evaluate"])
app.include_router(normalization.router, prefix="/api", tags=["Normalization"])


@app.get("/")
@limiter.limit("10/minute")  # Simple rate limit for health check
def read_root(request: Request):
    return {
        "message": "P-Auth RC is running",
        "version": "0.1.0",
        "authentication": "enabled"
    }


@app.get("/health")
def health_check():
    """Health check endpoint (no rate limit for monitoring)."""
    return {"status": "healthy"}
    