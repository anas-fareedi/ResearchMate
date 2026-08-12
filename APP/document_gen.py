import sys
import os
from pathlib import Path
from fpdf import FPDF
from typing import Dict, List, Optional
from datetime import datetime
import json
from config import OUTPUT_CONFIG, SEARCH_CONFIG
from utils import log_error, logger


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# M6 – anchor OUTPUT_DIR to the project root so it is stable regardless
#      of the working directory from which the server is launched.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = str(_PROJECT_ROOT / OUTPUT_CONFIG.get("directory", "research_outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── PDF layout constants ────────────────────────────────────────────────────
# A4 page height in mm minus header (≈20 mm) and footer (≈15 mm) margins.
# Used to estimate whether we've filled at least N pages.
_A4_BODY_HEIGHT_MM = 297 - 20 - 15 - 20  # ≈ 242 mm of usable body

# Approximate mm consumed by one line of 10-pt body text at 5-mm line height
_LINE_HEIGHT_MM = 5

# Characters that fit on one line at 10 pt in an A4 body (≈ 190 mm wide,
# Arial 10 pt ≈ 0.35 mm/char → ~543 chars/line, but wrapping makes it ~80
# printable chars per logical line).
_CHARS_PER_LINE = 85
_LINES_PER_PAGE = int(_A4_BODY_HEIGHT_MM / _LINE_HEIGHT_MM)  # ≈ 48




class PDFReport(FPDF):
    """Custom PDF class for research reports."""

    def header(self):
        self.set_font("Arial", "B", 14)
        self.set_fill_color(30, 30, 30)
        self.set_text_color(255, 255, 255)
        self.cell(0, 12, "Research Report", 0, 1, "C", fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")
        self.set_text_color(0, 0, 0)

    def section_heading(self, title: str):
        """Bold section heading with a subtle underline rule."""
        self.set_font("Arial", "B", 13)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 9, title, 0, 1, "L", fill=True)
        self.ln(2)

    def source_heading(self, number: int, title: str):
        """Numbered source title in bold."""
        self.set_font("Arial", "B", 11)
        self.cell(0, 8, f"Source {number}: {title}", 0, 1, "L")

    def source_url(self, url: str):
        """URL line in italic, smaller font."""
        self.set_font("Arial", "I", 9)
        self.set_text_color(30, 80, 160)
        self.cell(0, 6, url, 0, 1, "L", link=url)
        self.set_text_color(0, 0, 0)

    def body_text(self, text: str):
        """Regular body paragraph."""
        self.set_font("Arial", "", 10)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def divider(self):
        """Thin horizontal divider between sources."""
        self.set_draw_color(180, 180, 180)
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())
        self.ln(3)


def save_to_json(data: Dict, query: str) -> str:
    """
    Save research data to JSON file.

    Args:
        data: Research data dictionary
        query: Research query

    Returns:
        Path to saved JSON file

    Raises:
        Exception: If save fails
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_{timestamp}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)

        output = {
            "query": query,
            "timestamp": timestamp,
            "data": data,
        }

        json_indent = OUTPUT_CONFIG.get("json_indent", 2)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=json_indent, ensure_ascii=False)

        logger.info(f"JSON saved: {filepath}")
        return filepath
    except Exception as e:
        log_error(e, "save_to_json")
        raise


def clean_text_for_pdf(text: str) -> str:
    """Clean text to make it compatible with FPDF (latin-1 encoding)."""
    if not text:
        return ""

    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        "\u2013": "-",
        "\u2014": "--",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "\u2022": "*",
        "\u00b7": "*",
        "\u00ae": "(R)",
        "\u00a9": "(C)",
        "\u2122": "(TM)",
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)

    # Remove any remaining non-latin-1 characters
    # Bug #12 – If text still has non-latin-1 characters after the replacement
    # table, encode with 'replace' so that *every* replacement becomes a visible
    # '?' and we also emit a WARNING rather than silently mangling the text.
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        original_length = len(text)
        text = text.encode("latin-1", errors="replace").decode("latin-1")
        replaced_count = sum(1 for c in text if c == "?")
        if replaced_count:
            import logging as _logging

            _logging.getLogger(__name__).warning(
                "clean_text_for_pdf: %d non-Latin-1 character(s) replaced with '?' "
                "(original length %d). Consider switching to a Unicode-capable PDF font.",
                replaced_count,
                original_length,
            )
    return text


def _has_meaningful_content(item: Dict) -> bool:
    """Return True when a source item has usable extracted content for PDF output."""
    title = (item.get("title") or "").strip().lower()
    content = (item.get("content") or "").strip()

    if len(content) < 150:
        return False
    if title.startswith("error"):
        return False
    if content.lower().startswith("failed to extract"):
        return False
    if content.lower().startswith("url validation failed"):
        return False
    return True


def _clean_content_text(raw: str, max_chars: int) -> str:
    """
    Return a PDF-safe excerpt of *raw* that:
    - strips blank/whitespace-only lines
    - collapses runs of whitespace within lines
    - removes obvious navigation/boilerplate fragments (short lines < 4 words)
    - is capped at *max_chars* characters
    """
    lines = raw.splitlines()
    cleaned_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip very short navigation-style lines (< 4 words) that are just
        # menu items / cookie banners / "Skip to content" etc.
        words = stripped.split()
        if len(words) < 4:
            continue
        cleaned_lines.append(" ".join(words))

    text = " ".join(cleaned_lines)
    if len(text) > max_chars:
        # Trim at a sentence boundary if possible
        cut = text[:max_chars]
        last_period = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        if last_period > max_chars * 0.7:
            cut = cut[: last_period + 1]
        text = cut
    return text


def _write_source_block(
    pdf: PDFReport,
    number: int,
    item: Dict,
    chars_per_source: int,
    font: str,
) -> None:
    """Write a single numbered source block (heading + URL + body) to *pdf*."""
    title = clean_text_for_pdf((item.get("title") or "Untitled").strip())
    url = clean_text_for_pdf((item.get("url") or "").strip())
    raw_content = item.get("content") or ""
    body = clean_text_for_pdf(_clean_content_text(raw_content, chars_per_source))

    pdf.source_heading(number, title)
    if url:
        pdf.source_url(url)
    if body:
        pdf.body_text(body)
    pdf.divider()


def save_to_pdf(data: Dict, query: str, summary: str) -> str:
    """
    Save research data to PDF file.

    Strategy:
    1. Write query title + AI summary.
    2. Write valid sources (up to pdf_chars_per_source chars each).
    3. If the document is still under pdf_min_pages after exhausting the
       primary content list, pull in additional sources from the fallback
       list (remaining validated sources ranked by content length) until
       the page target is met or all sources are exhausted.

    Args:
        data: Research data dictionary (must contain 'content' list of dicts
              with 'title', 'url', 'content' keys)
        query: Research query string
        summary: AI-generated summary text

    Returns:
        Path to saved PDF file

    Raises:
        Exception: If save fails
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_{timestamp}.pdf"
        filepath = os.path.join(OUTPUT_DIR, filename)

        font = OUTPUT_CONFIG.get("pdf_font", "Arial")
        chars_per_source = SEARCH_CONFIG.get("pdf_chars_per_source", 3000)
        min_pages = SEARCH_CONFIG.get("pdf_min_pages", 3)

        # ── Partition sources ──────────────────────────────────────────────
        all_content = data.get("content", [])
        valid_sources = [s for s in all_content if _has_meaningful_content(s)]

        # Sort so the richest sources appear first; this is the "primary" list.
        valid_sources.sort(key=lambda s: len(s.get("content") or ""), reverse=True)

        pdf = PDFReport()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # ── Title ──────────────────────────────────────────────────────────
        pdf.set_font(font, "B", 15)
        pdf.multi_cell(0, 9, clean_text_for_pdf(f"Research Query: {query}"))
        pdf.ln(4)

        # ── Summary section ───────────────────────────────────────────────
        if summary and summary.strip():
            pdf.section_heading("Summary")
            summary_clean = clean_text_for_pdf(
                _clean_content_text(summary, max_chars=4000)
            )
            pdf.body_text(summary_clean)
            pdf.ln(2)

        # ── Sources section ───────────────────────────────────────────────
        pdf.section_heading("Sources and Content")

        written_count = 0
        for item in valid_sources:
            _write_source_block(pdf, written_count + 1, item, chars_per_source, font)
            written_count += 1

        # ── Fallback: keep adding sources until we reach min_pages ────────
        # If after exhausting valid_sources we are still below the page
        # threshold, extract from any remaining raw sources (lower-ranked,
        # shorter content) so the PDF always contains at least min_pages pages.
        if pdf.page_no() < min_pages:
            logger.info(
                f"PDF is only {pdf.page_no()} page(s) after primary sources. "
                f"Activating fallback to reach {min_pages} pages."
            )

            # Build fallback pool: all content items not already written,
            # ordered from longest to shortest
            written_urls = {s.get("url") for s in valid_sources}
            fallback_pool = [
                s for s in all_content
                if s.get("url") not in written_urls and (s.get("content") or "")
            ]
            fallback_pool.sort(key=lambda s: len(s.get("content") or ""), reverse=True)

            for item in fallback_pool:
                if pdf.page_no() >= min_pages:
                    break
                content = (item.get("content") or "").strip()
                if len(content) < 80:
                    continue
                _write_source_block(pdf, written_count + 1, item, chars_per_source, font)
                written_count += 1

        # ── Page padding: if still short, repeat existing content in full ─
        # Last-resort: if we have valid sources but the PDF is still short,
        # re-emit them without truncation to fill remaining pages.
        if pdf.page_no() < min_pages and valid_sources:
            logger.info(
                f"PDF still at {pdf.page_no()} page(s). Expanding source content to fill pages."
            )
            for item in valid_sources:
                if pdf.page_no() >= min_pages:
                    break
                # Use full content (no char cap) for this expansion pass
                full_body = clean_text_for_pdf(
                    _clean_content_text(item.get("content") or "", max_chars=10000)
                )
                if full_body:
                    pdf.body_text(full_body)

        # ── References section (IEEE-style, from citations list) ────────────
        citations = data.get("citations", [])

        if not citations:
            # Fall back: build citations from valid_sources if agent didn't provide them
            from datetime import datetime as _dt
            _today = _dt.utcnow().strftime("%Y-%m-%d")
            citations = [
                {
                    "number": idx,
                    "title": (s.get("title") or s.get("url") or f"Source {idx}").strip(),
                    "url": (s.get("url") or "").strip(),
                    "accessed": _today,
                }
                for idx, s in enumerate(valid_sources, start=1)
                if s.get("url")
            ]

        if citations:
            pdf.section_heading("References")
            pdf.set_font(font, "", 9)
            for cite in citations:
                num = cite.get("number", "?")
                title = clean_text_for_pdf(cite.get("title") or "Untitled")
                url = clean_text_for_pdf(cite.get("url") or "")
                accessed = cite.get("accessed", "")

                # IEEE format: [N] Title. [Online]. Available: URL. Accessed: DATE.
                line = f"[{num}] {title}."
                if url:
                    line += f" [Online]. Available: {url}."
                if accessed:
                    line += f" Accessed: {accessed}."

                pdf.multi_cell(0, 5, clean_text_for_pdf(line))
                pdf.ln(1)

        pdf.output(filepath)
        logger.info(
            f"PDF saved: {filepath}  ({pdf.page_no()} pages, {written_count} sources, "
            f"{len(citations)} citations)"
        )
        return filepath
    except Exception as e:
        log_error(e, "save_to_pdf")
        raise
