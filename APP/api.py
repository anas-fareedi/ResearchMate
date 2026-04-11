
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from typing import List, Optional
from research import research

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

_raw_allowed_origins = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
)
_allowed_origins = [origin.strip() for origin in _raw_allowed_origins.split(",") if origin.strip()]
if not _allowed_origins:
    _allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    websites: Optional[List[str]] = None


@app.post("/research")
def run_research(request: QueryRequest):
    result = research(request.query, request.websites)
    return result

_OUTPUT_DIR = (Path(__file__).resolve().parent.parent / "research_outputs").resolve()


@app.get("/download-pdf")
def download_pdf(filename: str):
    safe_name = Path(filename).name
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    target = (_OUTPUT_DIR / safe_name).resolve()
    if target.parent != _OUTPUT_DIR:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(target), media_type="application/pdf", filename=safe_name)
