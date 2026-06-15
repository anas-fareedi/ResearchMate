# ============================================================
# app.py  –  Research Assistant FastAPI backend
# ============================================================

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import asyncio
import ipaddress
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4
from supabase import create_client, Client

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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
# Rate limiter (slowapi)
# ---------------------------------------------------------------------------
_limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# FastAPI app + CORS
# ---------------------------------------------------------------------------
_app_dependencies = [Depends(_api_token_dependency)] if settings.API_ACCESS_TOKEN else []
app = FastAPI(title="Research Assistant API", version="1.0.0", dependencies=_app_dependencies)

# Attach the limiter and its exception handler
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
# Security helpers
# ---------------------------------------------------------------------------

# Private / loopback IP ranges that website URLs must NOT resolve to
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]
_URL_RE = re.compile(
    r"^https?://"                   # must start with http:// or https://
    r"[a-zA-Z0-9\-\.]+"             # hostname
    r"(\.[a-zA-Z]{2,})?"            # TLD
    r"(:[0-9]{1,5})?"               # optional port
    r"(/[^\s]*)?$",                 # optional path (no whitespace)
    re.IGNORECASE,
)

# Characters that should never appear in a research query
_QUERY_BLACKLIST_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _validate_website_url(url: str) -> str:
    """
    Validate a user-supplied website URL.

    Rejects:
    - Non-HTTP(S) schemes (file://, ftp://, etc.)
    - Bare IP addresses that fall in private/loopback ranges (SSRF guard)
    - URLs that don't match the basic URL pattern

    Returns the validated URL, or raises HTTPException 422.
    """
    if not _URL_RE.match(url):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid website URL: '{url}'. Must be a valid http(s):// URL.",
        )
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    # SSRF guard: reject bare private-IP hostnames
    try:
        addr = ipaddress.ip_address(hostname)
        if any(addr in net for net in _PRIVATE_NETWORKS):
            raise HTTPException(
                status_code=422,
                detail=f"Website URL '{url}' resolves to a private/reserved address.",
            )
    except ValueError:
        pass  # hostname is a domain name — allowed
    return url


def _sanitize_query(query: str) -> str:
    """
    Strip null-bytes, C0 control characters, and excessive whitespace from
    the research query so they cannot be injected into LLM prompts or logs.
    """
    query = _QUERY_BLACKLIST_RE.sub("", query)
    # Collapse runs of whitespace (keep single spaces / newlines)
    query = re.sub(r" {2,}", " ", query).strip()
    return query


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    # #7 – length constraints prevent excessively large request bodies
    query: str = Field(..., min_length=1, max_length=2000)
    # H6 – cap websites list to prevent DoS via thousands of scrape targets
    websites: Optional[List[str]] = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def validate_fields(self):
        # Sanitize query
        self.query = _sanitize_query(self.query)
        if not self.query:
            raise ValueError("query must not be empty after sanitization")
        # Validate each website URL
        if self.websites:
            validated = []
            for url in self.websites:
                cleaned = url.strip()
                if not cleaned or cleaned.lower() == "string":
                    continue
                try:
                    validated.append(_validate_website_url(cleaned))
                except HTTPException as exc:
                    raise ValueError(exc.detail) from exc
            self.websites = validated if validated else None
        return self


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str  # always "queued" on creation
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str              # queued | running | completed | failed
    message: Optional[str] = None
    progress: Optional[int] = None   # 0-100



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
    document_id: str
    filename: str
    local_path: Optional[str] = None
    supabase_url: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[Dict]


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

_DOCUMENT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Lazy initialize Supabase client if keys are configured."""
    global _supabase_client
    if _supabase_client is None:
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            try:
                url = settings.SUPABASE_URL.strip()
                if url.endswith("/"):
                    url = url.rstrip("/")
                if url.endswith("/rest/v1"):
                    url = url[:-8]
                if url.endswith("/"):
                    url = url.rstrip("/")

                _supabase_client = create_client(url, settings.SUPABASE_KEY)
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
    return _supabase_client


def _download_from_supabase_storage(document_id: str) -> Optional[str]:
    """Try to download PDF from Supabase Storage and cache it locally."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        bucket = client.storage.from_(settings.SUPABASE_BUCKET)
        files = bucket.list()
        for f in files:
            name = f.get("name", "")
            if not name.lower().endswith(".pdf"):
                continue
            
            # Check if name matches pattern docid_filename.pdf or docid.pdf
            parts = name.split("_", 1)
            is_match = False
            if len(parts) == 2 and parts[0] == document_id:
                is_match = True
            elif Path(name).stem == document_id:
                is_match = True
                
            if is_match:
                logger.info(f"Found document {name} in Supabase Storage. Downloading...")
                file_data = bucket.download(name)
                
                _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                local_path = _OUTPUT_DIR / name
                with open(local_path, "wb") as local_file:
                    local_file.write(file_data)
                logger.info(f"Successfully cached {name} locally at {local_path}")
                return str(local_path)
    except Exception as e:
        logger.error(f"Error downloading {document_id} from Supabase: {e}")
    return None


def _save_pdf_locally(file_path: str, filename: str, metadata: Optional[Dict] = None) -> Dict:
    """Save PDF to local disk and upload to Supabase Storage if configured."""
    safe_filename = Path(filename).name
    doc_id = str(uuid4())

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = _OUTPUT_DIR / f"{doc_id}_{safe_filename}"
    shutil.copy(file_path, local_path)

    supabase_url = None
    client = get_supabase_client()
    if client:
        try:
            storage_path = f"{doc_id}_{safe_filename}"
            with open(local_path, "rb") as f:
                file_data = f.read()
            client.storage.from_(settings.SUPABASE_BUCKET).upload(
                path=storage_path,
                file=file_data,
                file_options={"content-type": "application/pdf"}
            )
            supabase_url = client.storage.from_(settings.SUPABASE_BUCKET).get_public_url(storage_path)
            logger.info(f"Uploaded {storage_path} to Supabase Storage: {supabase_url}")
        except Exception as e:
            logger.error(f"Failed to upload {safe_filename} to Supabase Storage: {e}")

    record: Dict = {
        "filename": safe_filename,
        "local_path": str(local_path),
        "supabase_url": supabase_url,
        "document_id": doc_id,
        "created_at": str(Path(file_path).stat().st_mtime),
        "source": "local" if not supabase_url else "supabase",
    }
    if metadata:
        # M3 – never let caller metadata silently overwrite core identity fields
        protected = {"filename", "local_path", "supabase_url", "document_id", "created_at", "source"}
        record.update({k: v for k, v in metadata.items() if k not in protected})

    return record


def _get_local_document_path(document_id: str) -> str:
    """Get local PDF path using its document_id, downloading from Supabase if needed."""
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

    # Try downloading from Supabase if not found locally (stateless backend support)
    downloaded_path = _download_from_supabase_storage(document_id)
    if downloaded_path:
        return downloaded_path

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
    except Exception:
        # Improvement #1 – surface a user-friendly message instead of a raw
        # exception traceback so the client can display actionable text.
        raise HTTPException(
            status_code=503,
            detail="Search provider unavailable. Please try again later.",
        )

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


# ---------------------------------------------------------------------------
# Improvement #2 – Server-Sent Events endpoint for real-time progress
# ---------------------------------------------------------------------------

_PROGRESS_STAGES = [
    ("planning",    "Planning Research..."),
    ("searching",   "Searching Sources..."),
    ("extracting",  "Extracting Content..."),
    ("summarizing", "Generating Report..."),
    ("saving",      "Creating PDF..."),
    ("done",        "Done"),
]


async def _sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


async def _research_stream_generator(
    query: str, websites: Optional[List[str]]
) -> AsyncGenerator[str, None]:
    """Run the research workflow in a thread and stream progress via SSE."""
    import concurrent.futures

    loop = asyncio.get_event_loop()
    result_container: Dict = {}
    error_container: Dict = {}

    # Stage indices so we can emit progress events as each stage completes
    stage_names = [s[0] for s in _PROGRESS_STAGES]

    # Emit the first stage immediately so the client sees activity right away
    yield await _sse_event({"stage": "planning", "message": "Planning Research...", "progress": 0})

    def _run() -> dict:
        """Blocking call – executed in a thread pool so the event loop stays free."""
        return research(query, websites)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = loop.run_in_executor(pool, _run)

        # While the research task is running, emit heartbeat progress events
        # that map roughly to the five workflow stages.
        # Each stage is ~5 s apart (total ≈ 25 s observed).  We advance through
        # the stages pseudo-sequentially so the UI looks alive.
        stage_index = 1  # 0 was already emitted above
        elapsed = 0.0
        stage_interval = 5.0  # seconds between synthetic stage advances

        while not future.done():
            await asyncio.sleep(1.0)
            elapsed += 1.0

            # Advance to the next stage label on a timer
            next_stage_time = stage_index * stage_interval
            if elapsed >= next_stage_time and stage_index < len(_PROGRESS_STAGES) - 1:
                stage_key, stage_msg = _PROGRESS_STAGES[stage_index]
                progress = int((stage_index / (len(_PROGRESS_STAGES) - 1)) * 100)
                yield await _sse_event({"stage": stage_key, "message": stage_msg, "progress": progress})
                stage_index += 1

        # Collect result or error
        try:
            result = future.result()
            result_container.update(result)
        except Exception as exc:
            error_container["error"] = str(exc)

    if error_container:
        yield await _sse_event({
            "stage": "error",
            "message": "Search provider unavailable. Please try again later.",
            "progress": 0,
        })
        return

    # Emit the "done" event with the full result payload (including sources)
    yield await _sse_event({
        "stage": "done",
        "message": "Done",
        "progress": 100,
        "result": result_container,
    })


@app.post("/research/stream")
async def run_research_stream(request: QueryRequest):
    """Stream research progress as Server-Sent Events (text/event-stream).

    Clients should listen to this endpoint instead of POST /research when they
    want real-time progress feedback.  Each event is a JSON object with at least
    ``stage`` and ``message`` fields.  The final ``done`` event also carries the
    full ``result`` payload (same shape as POST /research).
    """
    return StreamingResponse(
        _research_stream_generator(request.query, request.websites),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Async Job Queue  –  POST /jobs, GET /jobs/{id}, GET /jobs/{id}/result
# ---------------------------------------------------------------------------
# The Celery import is deferred and guarded so the API still starts
# (with degraded job-queue support) even when Redis is not available.

_celery_available = False
try:
    from tasks import run_research_task
    from celery.result import AsyncResult
    from celery_app import celery_app as _celery_app
    _celery_available = True
except Exception as _celery_import_err:   # noqa: BLE001
    logger.warning(
        "Celery/Redis not available — /jobs endpoints will return 503. "
        "Start Redis and install celery[redis] to enable async jobs. "
        "Error: %s", _celery_import_err,
    )


def _require_celery():
    if not _celery_available:
        raise HTTPException(
            status_code=503,
            detail=(
                "Async job queue is not available. "
                "Ensure Redis is running and celery[redis] is installed."
            ),
        )


_CELERY_TO_API_STATUS = {
    "PENDING":  "queued",
    "RECEIVED": "queued",
    "STARTED":  "running",
    "PROGRESS": "running",
    "RETRY":    "running",
    "SUCCESS":  "completed",
    "FAILURE":  "failed",
    "REVOKED":  "failed",
}

_RATE_LIMIT = f"{settings.RATE_LIMIT_PER_MINUTE}/minute"


@app.post("/jobs", response_model=JobSubmitResponse, status_code=202)
@_limiter.limit(_RATE_LIMIT)
async def submit_job(request: Request, body: QueryRequest):
    """
    Submit a research job and return a job_id immediately.

    The heavy work runs inside a Celery worker.  Poll GET /jobs/{job_id}
    for status updates and GET /jobs/{job_id}/result for the final report.

    Rate-limited to RATE_LIMIT_PER_MINUTE submissions per IP per minute.
    """
    _require_celery()
    task = run_research_task.apply_async(
        kwargs={"query": body.query, "websites": body.websites},
        queue="research",
    )
    logger.info("Job submitted: %s  query=%.80s", task.id, body.query)
    return JobSubmitResponse(
        job_id=task.id,
        status="queued",
        message="Research job created. Poll GET /jobs/{job_id} for progress.",
    )


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """
    Poll the status of a submitted research job.

    Returns one of: queued | running | completed | failed
    When status is 'running', an optional progress (0-100) and message are
    included from the PROGRESS meta dict emitted by the Celery task.
    """
    _require_celery()
    # Validate job_id to prevent arbitrary Redis key probing
    if not re.match(r"^[a-fA-F0-9\-]{8,64}$", job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    result = AsyncResult(job_id, app=_celery_app)
    celery_state = result.state          # e.g. 'PENDING', 'PROGRESS', 'SUCCESS'
    api_status = _CELERY_TO_API_STATUS.get(celery_state, "queued")

    progress: Optional[int] = None
    message: Optional[str] = None

    if celery_state == "PROGRESS":
        meta = result.info or {}
        progress = meta.get("progress")
        message = meta.get("message")
    elif celery_state == "SUCCESS":
        progress = 100
        message = "Done"
    elif celery_state == "FAILURE":
        message = "Search provider unavailable. Please try again later."

    return JobStatusResponse(
        job_id=job_id,
        status=api_status,
        message=message,
        progress=progress,
    )


@app.get("/jobs/{job_id}/result")
def get_job_result(job_id: str):
    """
    Fetch the final result of a completed research job.

    Returns HTTP 404 if the job is not yet complete, and HTTP 200 with the
    same payload shape as POST /research on success (json_path, pdf_path,
    summary, sources).
    """
    _require_celery()
    if not re.match(r"^[a-fA-F0-9\-]{8,64}$", job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    result = AsyncResult(job_id, app=_celery_app)

    if result.state == "FAILURE":
        raise HTTPException(
            status_code=503,
            detail="Search provider unavailable. Please try again later.",
        )
    if result.state != "SUCCESS":
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' is not yet complete (status: {result.state.lower()}).",
        )

    payload = result.get(propagate=False) or {}

    # Optionally persist the PDF locally (mirrors the logic in POST /research)
    pdf_path = payload.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        try:
            local_doc = _save_pdf_locally(
                file_path=pdf_path,
                filename=Path(pdf_path).name,
                metadata={
                    "job_id": job_id,
                    "summary": payload.get("summary", ""),
                    "source": "generated",
                },
            )
            payload["local"] = local_doc
        except Exception as exc:
            logger.warning("Could not persist PDF locally for job %s: %s", job_id, exc)

    return payload


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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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

    # Try Supabase first if configured
    client = get_supabase_client()
    if client:
        try:
            bucket = client.storage.from_(settings.SUPABASE_BUCKET)
            files = bucket.list()
            for f in files:
                name = f.get("name", "")
                if not name.lower().endswith(".pdf"):
                    continue
                parts = name.split("_", 1)
                if len(parts) == 2 and len(parts[0]) == 36:
                    doc_id, filename = parts
                else:
                    doc_id = Path(name).stem
                    filename = name

                created_at = f.get("created_at") or f.get("updated_at") or "0"
                items.append({
                    "document_id": doc_id,
                    "filename": filename,
                    "supabase_url": bucket.get_public_url(name),
                    "created_at": created_at,
                    "source": "supabase",
                })
            items.sort(key=lambda x: x.get("created_at", "0"), reverse=True)
            return DocumentListResponse(documents=items[:limit])
        except Exception as e:
            logger.error(f"Failed to list documents from Supabase storage: {e}. Falling back to local.")

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
        # Try to download from Supabase Storage to local cache
        parts = safe_name.split("_", 1)
        doc_id = parts[0] if (len(parts) == 2 and len(parts[0]) == 36) else Path(safe_name).stem
        downloaded = _download_from_supabase_storage(doc_id)
        if not downloaded or not Path(downloaded).exists():
            raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(target), media_type="application/pdf", filename=safe_name)