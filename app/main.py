"""
FastAPI application entry point.
Mounts the single router. Loads env vars.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

# Load .env from project root, regardless of where the app is started from
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

from app.router import router

app = FastAPI(title="P-Auth RC")
app.include_router(router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "P-Auth RC is running"}
