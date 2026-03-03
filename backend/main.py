"""FastAPI entry point for PaperTales."""

import os
from pathlib import Path

from google.adk.cli.fast_api import get_fast_api_app

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

app = get_fast_api_app(
    agents_dir=str(Path(__file__).parent),
    web=True,
    allow_origins=CORS_ORIGINS.split(","),
)


@app.get("/health")
async def health():
    return {"status": "ok"}
