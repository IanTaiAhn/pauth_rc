from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import rag, documents, pa, authz, normalization

app = FastAPI(title="P-Auth RC")

# ---------------------------------------------------------
# CORS MUST BE ADDED BEFORE ROUTES
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
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
def read_root():
    return {"message": "P-Auth RC is running"}
    