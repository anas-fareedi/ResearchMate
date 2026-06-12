# ============================================================
# app.py  –  Research Assistant FastAPI backend
# ============================================================

import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from qa_chat import PDFRAGChatbot
from research import research
from config import settings
from utils import logger

# ---------------------------------------------------------------------------
# Load .env from project root is handled by pydantic-settings in config.py
# ---------------------------------------------------------------------------

_OUTPUT_DIR = (Path(__file__).resolve().parent.parent / "research_outputs").resolve()
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # ensure it exists at startup
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _api_token_dependency(x_api_token: Optional[str] = Header(default=None)):
    expected_token = settings.API_ACCESS_TOKEN
    if expected_token and x_api_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid API access token")


# ---------------------------------------------------------------------------
# FastAPI app + CORS
# ---------------------------------------------------------------------------
_app_dependencies = [Depends(_api_token_dependency)] if settings.API_ACCESS_TOKEN else []
app = FastAPI(title="Research Assistant API", version="1.0.0", dependencies=_app_dependencies)

_raw_allowed_origins = settings.CORS_ALLOW_ORIGINS
_allowed_origins = [o.strip() for o in _raw_allowed_origins.split(",") if o.strip()]
if not _allowed_origins:
    _allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    # #7 – length constraints prevent excessively large request bodies
    query: str = Field(..., min_length=1, max_length=2000)
    # H6 – cap websites list to prevent DoS via thousands of scrape targets
    websites: Optional[List[str]] = Field(default=None, max_length=20)


class QARequest(BaseModel):
    # M1 – unbounded question enables token-cost abuse and prompt injection
    question: str = Field(..., min_length=1, max_length=1000)
    pdf_path: Optional[str] = None
    document_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_pdf_source(self):
        if not self.pdf_path and not self.document_id:
            raise ValueError("Provide either 'pdf_path' or 'document_id'")
        return self


class UploadPdfResponse(BaseModel):
    # L2 – removed download_url / storage_path; they were Firebase-only fields
    #       always set to None after the Firebase removal.
    document_id: str
    filename: str
    local_path: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[Dict]


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

_DOCUMENT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def _save_pdf_locally(file_path: str, filename: str, metadata: Optional[Dict] = None) -> Dict:
    """Save PDF to local disk."""
    safe_filename = Path(filename).name
    doc_id = str(uuid4())

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = _OUTPUT_DIR / f"{doc_id}_{safe_filename}"
    shutil.copy(file_path, local_path)

    record: Dict = {
        "filename": safe_filename,
        "local_path": str(local_path),
        "document_id": doc_id,
        "created_at": str(Path(file_path).stat().st_mtime),
        "source": "local",
    }
    if metadata:
        # M3 – never let caller metadata silently overwrite core identity fields
        protected = {"filename", "local_path", "document_id", "created_at", "source"}
        record.update({k: v for k, v in metadata.items() if k not in protected})

    return record


def _get_local_document_path(document_id: str) -> str:
    """Get local PDF path using its document_id."""
    # H1 – validate document_id before using it in a glob pattern;
    #       glob metacharacters (*?[) would otherwise match unintended files.
    if not _DOCUMENT_ID_RE.match(document_id):
        raise HTTPException(status_code=400, detail="Invalid document_id format")

    if _OUTPUT_DIR.exists():
        for pdf_file in _OUTPUT_DIR.glob(f"{document_id}_*.pdf"):
            return str(pdf_file)
        # Also support legacy files where the full stem equals the document_id
        for pdf_file in _OUTPUT_DIR.glob("*.pdf"):
            if pdf_file.stem == document_id:
                return str(pdf_file)

    raise HTTPException(status_code=404, detail="Document not found")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Welcome to the Research API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/research")
def run_research(request: QueryRequest):
    # Bug #6 – wrap the whole workflow in a try/except so callers always get a
    # structured HTTP error instead of a raw 500 traceback.
    try:
        result = research(request.query, request.websites)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research workflow failed: {exc}")

    pdf_path = result.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        local_doc = _save_pdf_locally(
            file_path=pdf_path,
            filename=Path(pdf_path).name,
            metadata={
                "query": request.query,
                "summary": result.get("summary", ""),
                "source": "generated",
            },
        )
        result["local"] = local_doc

    return result


@app.post("/qa")
def run_qa(request: QARequest):
    try:
        if request.document_id:
            source_pdf = _get_local_document_path(request.document_id)
        else:
            raw_path = request.pdf_path
            if not raw_path:
                raise HTTPException(status_code=400, detail="pdf_path is required")
            resolved = Path(raw_path).resolve()
            # H2 – enforce .pdf extension before any further path checks
            if resolved.suffix.lower() != ".pdf":
                raise HTTPException(status_code=400, detail="Only .pdf files are permitted")
            # #4 – path-traversal guard: must stay inside _OUTPUT_DIR
            if not resolved.is_relative_to(_OUTPUT_DIR):
                raise HTTPException(
                    status_code=403,
                    detail="Access to the requested path is not permitted"
                )
            if not resolved.exists():
                raise HTTPException(status_code=404, detail="Local PDF file not found")
            source_pdf = str(resolved)

        bot = PDFRAGChatbot(source_pdf)
        answer = bot.ask(request.question)
        return {"answer": answer}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/upload-pdf", response_model=UploadPdfResponse)
async def upload_pdf_for_qa(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    description: Optional[str] = None,
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    # #3 – create temp file; keep it alive until _save_pdf_locally returns,
    #       then always clean it up in the finally block.
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()   # close the handle; the file still exists on disk

    try:
        total_bytes = 0
        with open(tmp_path, "wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > _MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Uploaded PDF is too large")
                handle.write(chunk)

        record = _save_pdf_locally(
            file_path=tmp_path,
            filename=file.filename,
            metadata={
                "title": title or file.filename,
                "description": description or "Uploaded for Q&A",
                "source": "uploaded",
            },
        )
        # model_validate filters out extra keys (title, description, query, summary)
        # that _save_pdf_locally may carry but UploadPdfResponse does not declare.
        return UploadPdfResponse.model_validate(record)
    finally:
        try:
            await file.close()
        except Exception:
            pass
        # M4 – cleanup runs after _save_pdf_locally completes (success or failure)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


@app.get("/documents", response_model=DocumentListResponse)
def list_documents(limit: int = Query(default=50, ge=1, le=200)):
    items: List[Dict] = []

    # ── Local disk list ───────────────────────────────────────────────────
    if _OUTPUT_DIR.exists():
        for pdf_file in _OUTPUT_DIR.glob("*.pdf"):
            # Bug #8 – only treat the prefix as a document_id when it looks like
            # a UUID (36 chars).  Legacy filenames like "research_20260411.pdf"
            # are given a deterministic id from the full stem to avoid collisions.
            parts = pdf_file.name.split("_", 1)
            if len(parts) == 2 and len(parts[0]) == 36:
                doc_id, filename = parts
            else:
                doc_id = pdf_file.stem   # e.g. "research_20260411"
                filename = pdf_file.name

            items.append({
                "document_id": doc_id,
                "filename": filename,
                "local_path": str(pdf_file),
                "created_at": str(pdf_file.stat().st_mtime),
                "source": "local",
            })

        items.sort(key=lambda x: float(x.get("created_at", 0)), reverse=True)
        items = items[:limit]

    return DocumentListResponse(documents=items)


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