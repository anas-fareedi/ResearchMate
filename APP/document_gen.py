import sys
import os
from fpdf import FPDF
from typing import Dict
from datetime import datetime
import json
from config import OUTPUT_CONFIG
from utils import ensure_output_directory, log_error, logger


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = ensure_output_directory(OUTPUT_CONFIG.get("directory", "research_outputs"))


class PDFReport(FPDF):
    """Custom PDF class for research reports"""
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Research Report', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)
    
    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 5, body)
        self.ln()


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
            'query': query,
            'timestamp': timestamp,
            'data': data
        }
        
        json_indent = OUTPUT_CONFIG.get("json_indent", 2)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=json_indent, ensure_ascii=False)
        
        logger.info(f"JSON saved: {filepath}")
        return filepath
    except Exception as e:
        log_error(e, "save_to_json")
        raise


def clean_text_for_pdf(text: str) -> str:
    """Clean text to make it compatible with FPDF (latin-1 encoding)"""
    if not text:
        return ""
    
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2013': '-',      
        '\u2014': '--',     
        '\u2018': "'",     
        '\u2019': "'",     
        '\u201c': '"',      
        '\u201d': '"',     
        '\u2026': '...',    
        '\u00a0': ' ',     
        '\u2022': '*',      
        '\u00b7': '*',      
        '\u2019': "'",      
        '\u00ae': '(R)',    
        '\u00a9': '(C)',    
        '\u2122': '(TM)',   
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    
    # Remove any remaining non-latin-1 characters
    # Bug #12 – If text still has non-latin-1 characters after the replacement
    # table, encode with 'replace' so that *every* replacement becomes a visible
    # '?' and we also emit a WARNING rather than silently mangling the text.
    try:
        text.encode('latin-1')
    except UnicodeEncodeError:
        original_length = len(text)
        # Replace each un-encodable character with '?'
        text = text.encode('latin-1', errors='replace').decode('latin-1')
        replaced_count = sum(1 for c in text if c == '?')
        if replaced_count:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "clean_text_for_pdf: %d non-Latin-1 character(s) replaced with '?' "
                "(original length %d). Consider switching to a Unicode-capable PDF font.",
                replaced_count, original_length,
            )
    return text


def _has_meaningful_content(item: Dict) -> bool:
    """Return True when a source item has usable extracted content for PDF output."""
    title = (item.get('title') or '').strip().lower()
    content = (item.get('content') or '').strip()

    if not content:
        return False
    if title.startswith('error'):
        return False
    if content.lower().startswith('failed to extract'):
        return False
    if content.lower().startswith('url validation failed'):
        return False
    return True


def save_to_pdf(data: Dict, query: str, summary: str) -> str:
    """
    Save research data to PDF file.
    
    Args:
        data: Research data dictionary
        query: Research query
        summary: Research summary
    
    Returns:
        Path to saved PDF file
    
    Raises:
        Exception: If save fails
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_{timestamp}.pdf"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        pdf = PDFReport()
        pdf.add_page()
        
        font = OUTPUT_CONFIG.get("pdf_font", "Arial")
        font_size = OUTPUT_CONFIG.get("pdf_font_size", 11)
        
        pdf.set_font(font, 'B', 16)
        pdf.cell(0, 10, clean_text_for_pdf(f'Research Query: {query}'), 0, 1)
        pdf.ln(5)
        
        pdf.chapter_title('Summary')
        pdf.chapter_body(clean_text_for_pdf(summary))
        
        # Content from each source
        pdf.chapter_title('Sources and Content')
        
        valid_sources = [item for item in data.get('content', []) if _has_meaningful_content(item)]

        for item in valid_sources:
            pdf.set_font(font, 'B', 11)
            title = clean_text_for_pdf(item.get('title', 'N/A'))
            pdf.cell(0, 8, f"Title: {title}", 0, 1)
            
            pdf.set_font(font, 'I', 9)
            url = clean_text_for_pdf(item.get('url', 'N/A'))
            pdf.cell(0, 6, f"URL: {url}", 0, 1)
            
            pdf.set_font(font, '', 10)
            content = clean_text_for_pdf(item.get('content', 'No content')[:800])
            pdf.multi_cell(0, 5, content)
            pdf.ln(3)

        if not valid_sources:
            pdf.set_font(font, '', 10)
            pdf.multi_cell(0, 5, "No valid source content was available to include in this section.")
        
        pdf.output(filepath)
        logger.info(f"PDF saved: {filepath}")
        return filepath
    except Exception as e:
        log_error(e, "save_to_pdf")
        raise
