"""
FastAPI application entry point.
Mounts the single router. Loads env vars.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

from app.router import router

app = FastAPI(title="P-Auth RC")
app.include_router(router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "P-Auth RC is running"}
