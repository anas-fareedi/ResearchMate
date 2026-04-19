from dotenv import load_dotenv
from typing import List, Optional
from research import research

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

import os
from pathlib import Path
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

class QARequest(BaseModel):
    pdf_path: str
    question: str

@app.get("/")
def root():
    return {"message": "Welcome to the Research API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/research")
def run_research(request: QueryRequest):
    result = research(request.query, request.websites)
    return result

@app.post("/qa")
def run_qa(request: QARequest):
    try:
        from qa_chat import PDFRAGChatbot
        bot = PDFRAGChatbot(request.pdf_path)
        answer = bot.ask(request.question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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