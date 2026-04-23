import os
import sys

# Must be before any local imports so Python can find the APP/ package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict, Optional
from Agents.workflow import build_research_workflow
from utils import sanitize_query, validate_websites, log_error, logger
from config import DEFAULT_WEBSITES


def research(query: str, websites: Optional[List[str]] = None) -> Dict:
    """
    Main function to run the research assistant.
    
    Args:
        query: The research question/topic
        websites: Optional list of websites to search. If None, uses defaults.
    
    Returns:
        Dictionary with paths to generated JSON and PDF files
    
    Raises:
        ValueError: If query is invalid
    """

    try:
        query = sanitize_query(query)
    except ValueError as e:
        log_error(e, "Query validation failed")
        raise
    
   
    if websites:
        validated_websites = validate_websites(websites)
        if not validated_websites:
            logger.warning("No valid websites provided, using defaults")
            websites = DEFAULT_WEBSITES
        else:
            websites = validated_websites
    else:
        websites = DEFAULT_WEBSITES
    
    # Bug #15 – truncate the query in log output so PII is not written
    # verbatim to stdout / any downstream log aggregation system.
    log_query = (query[:77] + "...") if len(query) > 80 else query
    logger.info(f"Starting Research: {log_query}")
    
    try:
        app = build_research_workflow()
        initial_state = {
            'query': query,
            'websites': websites,
            'search_terms': [],
            'urls_found': [],
            'content': [],
            'summary': '',
            'json_path': '',
            'pdf_path': '',
            'status': 'initialized',
            'messages': []
        }
        
        result = app.invoke(initial_state)
        
        logger.info("Research Complete!", extra={
            "json_path": result['json_path'],
            "pdf_path": result['pdf_path']
        })
        # Bug #16 – use textwrap.shorten for a unicode-safe, word-boundary
        # aware preview instead of a raw character-index slice.
        from textwrap import shorten as _shorten
        summary_preview = _shorten(result['summary'], width=200, placeholder="...")
        logger.info(f"Summary preview: {summary_preview}")
        
        return {
            'json_path': result['json_path'],
            'pdf_path': result['pdf_path'],
            'summary': result['summary']
        }
    except Exception as e:
        log_error(e, "Research workflow error")
        raise
