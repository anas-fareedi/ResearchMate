import os
import re
import threading
from dataclasses import dataclass
from typing import List, Tuple

from pypdf import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import API_CONFIG, LLM_CONFIG
from utils import validate_api_key, log_error


@dataclass
class TextChunk:
    index: int
    text: str


_CHUNKS_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _normalize_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[TextChunk]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be larger than overlap")

    cleaned = _normalize_text(text)
    if not cleaned:
        return []

    chunks: List[TextChunk] = []
    start = 0
    i = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunks.append(TextChunk(index=i, text=cleaned[start:end]))
        if end >= len(cleaned):
            break
        start = end - overlap
        i += 1
    return chunks


def _get_cached_chunks(pdf_path: str) -> List[TextChunk]:
    """Retrieve PDF chunks from memory cache if file has not changed."""
    try:
        mtime = os.path.getmtime(pdf_path)
    except OSError:
        mtime = 0.0

    cache_key = (pdf_path, mtime)
    with _CACHE_LOCK:
        if cache_key in _CHUNKS_CACHE:
            return _CHUNKS_CACHE[cache_key]

        # Prevent unbound memory growth (evict everything if cache becomes too large)
        if len(_CHUNKS_CACHE) > 32:
            _CHUNKS_CACHE.clear()

    # Perform PDF reading/extraction outside the lock to minimize contention
    reader = PdfReader(pdf_path)
    all_text: List[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            all_text.append(page_text)

    merged = "\n".join(all_text)
    chunks = _chunk_text(merged)

    with _CACHE_LOCK:
        _CHUNKS_CACHE[cache_key] = chunks
        return chunks


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _score_chunk(question: str, chunk: TextChunk) -> int:
    question_tokens = _tokenize(question)
    if not question_tokens:
        return 0
    chunk_lower = chunk.text.lower()
    return sum(1 for token in question_tokens if token in chunk_lower)


class PDFRAGChatbot:
    """Simple RAG chatbot over generated PDF reports."""

    def __init__(self, pdf_path: str):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        self.pdf_path = pdf_path
        self.chunks = self._load_chunks(pdf_path)
        if not self.chunks:
            raise ValueError("Insufficient content to perform Q&A")

        gemini_api_key = validate_api_key(API_CONFIG["gemini_api_key"], "GEMINI_API_KEY")
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_CONFIG["model"],
            temperature=0.2,
            max_output_tokens=LLM_CONFIG["max_tokens"],
            google_api_key=gemini_api_key,
        )

    def _load_chunks(self, pdf_path: str) -> List[TextChunk]:
        # Bug #11 – reject files that are too large before reading all pages into RAM.
        MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
        file_size = os.path.getsize(pdf_path)
        if file_size > MAX_PDF_BYTES:
            raise ValueError(
                f"PDF file is too large for Q&A ({file_size / 1_048_576:.1f} MB). "
                f"Limit is 50 MB."
            )

        return _get_cached_chunks(pdf_path)

    def _retrieve(self, question: str, top_k: int = 4) -> List[TextChunk]:
        scored: List[Tuple[int, TextChunk]] = []
        for chunk in self.chunks:
            score = _score_chunk(question, chunk)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            return [chunk for _, chunk in scored[:top_k]]

        # Fallback: if query terms do not match, return first chunks.
        return self.chunks[:top_k]

    def ask(self, question: str) -> str:
        relevant_chunks = self._retrieve(question)
        context = "\n\n".join(
            [f"[Chunk {chunk.index}] {chunk.text}" for chunk in relevant_chunks]
        )

        prompt = (
            "Answer from context only. If missing, say insufficient context.\n"
            f"Q: {question}\n"
            f"Context:\n{context}"
        )

        response = self.llm.invoke([HumanMessage(content=prompt)])
        return str(response.content).strip()


def start_pdf_qa_chat(pdf_path: str):
    """Start an interactive Q&A chat session over a generated PDF report."""
    try:
        bot = PDFRAGChatbot(pdf_path)
    except Exception as e:
        log_error(e, "start_pdf_qa_chat initialization")
        print(f"\n✗ Could not start Q&A chat: {e}")
        return

    print("\n" + "=" * 70)
    print("PDF Q&A CHAT (RAG)")
    print("=" * 70)
    print("Ask questions about the generated report.")
    print("Type 'exit' or 'quit' to leave chat.\n")

    while True:
        try:
            question = input("You: ").strip()
            if not question:
                continue
            if question.lower() in {"exit", "quit"}:
                print("Assistant: Ending Q&A chat.")
                break

            answer = bot.ask(question)
            print(f"\nAssistant: {answer}\n")
        except KeyboardInterrupt:
            print("\nAssistant: Chat interrupted by user.")
            break
        except Exception as e:
            log_error(e, "start_pdf_qa_chat loop")
            print(f"Assistant: Sorry, I hit an error while answering: {e}")
