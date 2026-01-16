from fastapi import FastAPI
from app.api.pa import router as pa_router

app = FastAPI(title="PAUTH RC MVP")

app.include_router(pa_router, prefix="/pa")
