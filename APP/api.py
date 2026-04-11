
import os
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import FileResponse
from typing import List, Optional
from app.research import research   # your function

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all for now
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

@app.get("/download-pdf")
def download_pdf(path: str):
    return FileResponse(path, media_type='application/pdf', filename="research.pdf")