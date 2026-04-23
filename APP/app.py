# ============================================================
# app.py  –  Research Assistant FastAPI backend
# ============================================================
# Fixes applied:
#  #1  – _OUTPUT_DIR moved to top (before any function that uses it)
#  #2  – SERVER_TIMESTAMP replaced with None in response dict
#  #3  – temp-file cleanup moved to a safe finally-only block
#  #4  – pdf_path path-traversal protection added
#  #5  – signed-URL fallback chain: make_public → signed URL → plain GCS URL
#  #6  – /research wrapped in try/except with proper HTTP errors
#  #7  – query field max_length=2000 constraint via Pydantic Field
#  #8  – UUID-aware filename split in local fallback of list_documents
#  #9  – temp file cleanup on Firestore doc missing storage_path
#  #13 – firebase_admin imports moved to top with all other imports
# ============================================================

import json
import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

import firebase_admin
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from firebase_admin import credentials, firestore, storage
from pydantic import BaseModel, Field, model_validator

from qa_chat import PDFRAGChatbot
from research import research

# ---------------------------------------------------------------------------
# Load .env from project root
# ---------------------------------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ---------------------------------------------------------------------------
# Bug #1 – _OUTPUT_DIR defined HERE, at the top, before any function uses it.
# Previously it was defined on line 321 (after route handlers that call it).
# ---------------------------------------------------------------------------
_OUTPUT_DIR = (Path(__file__).resolve().parent.parent / "research_outputs").resolve()


# ---------------------------------------------------------------------------
# FastAPI app + CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="Research Assistant API", version="1.0.0")

_raw_allowed_origins = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
)
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
    # Bug #7 – added min/max length constraints to prevent excessively large bodies
    query: str = Field(..., min_length=1, max_length=2000)
    websites: Optional[List[str]] = None


class QARequest(BaseModel):
    question: str
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
    download_url: Optional[str] = None
    storage_path: Optional[str] = None
    local_path: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[Dict]


# ---------------------------------------------------------------------------
# Firebase helpers
# ---------------------------------------------------------------------------

def _extract_project_from_db_url(db_url: Optional[str]) -> Optional[str]:
    if not db_url:
        return None
    try:
        host = urlparse(db_url).hostname or ""
        prefix = host.split(".", 1)[0]
        if prefix.endswith("-default-rtdb"):
            return prefix[: -len("-default-rtdb")]
        return None
    except Exception:
        return None


def _firebase_config() -> Dict[str, Optional[str]]:
    service_account_path = (
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    if not project_id and service_account_json:
        try:
            project_id = json.loads(service_account_json).get("project_id")
        except Exception:
            project_id = None

    if not project_id and service_account_path and Path(service_account_path).exists():
        try:
            with open(service_account_path, "r", encoding="utf-8") as handle:
                project_id = json.load(handle).get("project_id")
        except Exception:
            project_id = None

    if not project_id:
        project_id = _extract_project_from_db_url(
            os.getenv("FIREBASE_DATABASE_URL") or os.getenv("db_url")
        )

    storage_bucket = (
        os.getenv("FIREBASE_STORAGE_BUCKET")
        or os.getenv("FIREBASE_BUCKET")
        or (f"{project_id}.appspot.com" if project_id else None)
    )

    return {
        "service_account_path": service_account_path,
        "service_account_json": service_account_json,
        "project_id": project_id,
        "storage_bucket": storage_bucket,
    }


def _init_firebase():
    cfg = _firebase_config()
    service_account_path = cfg["service_account_path"]
    service_account_json = cfg["service_account_json"]
    storage_bucket = cfg["storage_bucket"]

    if not storage_bucket:
        return None, None

    try:
        if not firebase_admin._apps:
            cred = None
            if service_account_path:
                cred = credentials.Certificate(service_account_path)
            elif service_account_json:
                cred = credentials.Certificate(json.loads(service_account_json))

            if cred is not None:
                firebase_admin.initialize_app(cred, {"storageBucket": storage_bucket})
            else:
                firebase_admin.initialize_app(options={"storageBucket": storage_bucket})

        db_client = firestore.client()
        bucket_client = storage.bucket()
        return db_client, bucket_client
    except Exception as exc:
        print(f"WARNING: Firebase init failed: {exc}")
        return None, None


db, bucket = _init_firebase()


def _ensure_firebase_ready():
    if db is None or bucket is None:
        cfg = _firebase_config()
        has_path = bool(cfg["service_account_path"])
        has_json = bool(cfg["service_account_json"])
        has_bucket = bool(cfg["storage_bucket"])
        raise HTTPException(
            status_code=503,
            detail=(
                "Firebase is not configured. Set FIREBASE_STORAGE_BUCKET (or FIREBASE_BUCKET) and "
                "service account credentials via FIREBASE_SERVICE_ACCOUNT_PATH / "
                "GOOGLE_APPLICATION_CREDENTIALS / FIREBASE_SERVICE_ACCOUNT_JSON. "
                f"Detected: has_bucket={has_bucket}, has_path={has_path}, has_json={has_json}."
            ),
        )


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _save_pdf_to_firebase(file_path: str, filename: str, metadata: Optional[Dict] = None) -> Dict:
    """Save PDF to Firebase Storage + Firestore, or fall back to local disk."""
    safe_filename = Path(filename).name
    doc_id = str(uuid4())

    # ── Try Firebase first ────────────────────────────────────────────────
    if db is not None and bucket is not None:
        try:
            storage_path = f"pdfs/{doc_id}_{safe_filename}"
            blob = bucket.blob(storage_path)
            blob.upload_from_filename(file_path, content_type="application/pdf")

            # Bug #5 – three-level fallback for download URL:
            #   1. make_public (fails when Uniform bucket-level access is on)
            #   2. generate_signed_url (fails without a service-account credential)
            #   3. plain GCS URL (always works, requires appropriate IAM rules)
            download_url: Optional[str] = None
            try:
                blob.make_public()
                download_url = blob.public_url
            except Exception as public_err:
                print(f"INFO: make_public failed ({public_err}), trying signed URL.")
                try:
                    download_url = blob.generate_signed_url(
                        version="v4", expiration=timedelta(days=365)
                    )
                except Exception as sign_err:
                    # Fallback: plain GCS URL (bucket-level access or requester-pays)
                    download_url = (
                        f"https://storage.googleapis.com/{bucket.name}/{storage_path}"
                    )
                    print(f"INFO: Signed URL failed ({sign_err}), using plain GCS URL.")

            # Firestore record — note we store SERVER_TIMESTAMP only in Firestore.
            # Bug #2 – do NOT put SERVER_TIMESTAMP into the response dict; it is a
            # special sentinel that Pydantic/JSON cannot serialise.
            firestore_record = {
                "filename": safe_filename,
                "storage_path": storage_path,
                "download_url": download_url,
                "created_at": firestore.SERVER_TIMESTAMP,   # written to Firestore only
                "source": "firebase",
            }
            if metadata:
                firestore_record.update(metadata)

            doc_ref = db.collection("documents").document()
            doc_ref.set(firestore_record)

            # Build the response dict without the un-serialisable sentinel
            result: Dict = {
                k: v for k, v in firestore_record.items() if k != "created_at"
            }
            result["created_at"] = None   # client will see null; Firestore holds the real value
            result["document_id"] = doc_ref.id
            return result

        except Exception as exc:
            print(f"WARNING: Firebase upload failed ({exc}), falling back to local storage")

    # ── Fallback: local disk ──────────────────────────────────────────────
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
        record.update(metadata)

    return record


def _download_document_pdf(document_id: str) -> str:
    """Download PDF from Firebase Storage (via Firestore lookup) or local disk."""
    # ── Try Firebase ──────────────────────────────────────────────────────
    if db is not None:
        try:
            doc_ref = db.collection("documents").document(document_id)
            snapshot = doc_ref.get()
            if snapshot.exists:
                data = snapshot.to_dict() or {}
                storage_path = data.get("storage_path")
                if storage_path and bucket is not None:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    tmp.close()
                    try:
                        # Bug #9 – if download fails, clean up the temp file immediately
                        bucket.blob(storage_path).download_to_filename(tmp.name)
                        return tmp.name
                    except Exception as dl_err:
                        os.unlink(tmp.name)
                        print(f"WARNING: Firebase download failed ({dl_err}), trying local.")
        except Exception:
            pass  # fall through to local

    # ── Fallback: local disk ──────────────────────────────────────────────
    if _OUTPUT_DIR.exists():
        for pdf_file in _OUTPUT_DIR.glob(f"{document_id}_*.pdf"):
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


@app.get("/firebase-status")
def firebase_status():
    cfg = _firebase_config()
    return {
        "initialized": db is not None and bucket is not None,
        "has_storage_bucket": bool(cfg["storage_bucket"]),
        "has_service_account_path": bool(cfg["service_account_path"]),
        "has_service_account_json": bool(cfg["service_account_json"]),
        "project_id": cfg["project_id"],
        "storage_bucket": cfg["storage_bucket"],
    }


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
    if pdf_path and Path(pdf_path).exists() and db is not None and bucket is not None:
        firebase_doc = _save_pdf_to_firebase(
            file_path=pdf_path,
            filename=Path(pdf_path).name,
            metadata={
                "query": request.query,
                "summary": result.get("summary", ""),
                "source": "generated",
            },
        )
        result["firebase"] = firebase_doc

    return result


@app.post("/qa")
def run_qa(request: QARequest):
    temp_pdf_path = None
    try:
        if request.document_id:
            temp_pdf_path = _download_document_pdf(request.document_id)
            source_pdf = temp_pdf_path
        else:
            # Bug #4 – validate pdf_path is inside _OUTPUT_DIR to prevent path traversal
            raw_path = request.pdf_path
            if not raw_path:
                raise HTTPException(status_code=400, detail="pdf_path is required")
            resolved = Path(raw_path).resolve()
            if not str(resolved).startswith(str(_OUTPUT_DIR)):
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
    finally:
        # temp_pdf_path only exists for Firebase-downloaded files; always clean up
        if temp_pdf_path:
            try:
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
            except OSError:
                pass


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

    # Bug #3 – create the temp file and handle cleanup exclusively in finally.
    # The file is kept alive until _save_pdf_to_firebase returns fully.
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()   # close the handle; the file still exists on disk

    try:
        file_bytes = await file.read()
        with open(tmp_path, "wb") as handle:
            handle.write(file_bytes)

        record = _save_pdf_to_firebase(
            file_path=tmp_path,
            filename=file.filename,
            metadata={
                "title": title or file.filename,
                "description": description or "Uploaded for Q&A",
                "source": "uploaded",
            },
        )
        return UploadPdfResponse(**record)
    finally:
        # Cleanup runs after _save_pdf_to_firebase completes (success or failure)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


@app.get("/documents", response_model=DocumentListResponse)
def list_documents(limit: int = Query(default=50, ge=1, le=200)):
    items: List[Dict] = []

    if db is not None:
        try:
            docs = (
                db.collection("documents")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            for doc in docs:
                payload = doc.to_dict() or {}
                created_at = payload.get("created_at")
                if hasattr(created_at, "isoformat"):
                    payload["created_at"] = created_at.isoformat()
                payload["document_id"] = doc.id
                items.append(payload)
            return DocumentListResponse(documents=items)
        except Exception as exc:
            print(f"WARNING: Firestore fetch failed ({exc}), falling back to local storage")

    # ── Fallback: local disk ──────────────────────────────────────────────
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