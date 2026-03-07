import os
import sys
from typing import List, Dict, Optional
from Agents.workflow import build_research_workflow
from utils import sanitize_query, validate_websites, log_error
from config import DEFAULT_WEBSITES

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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
    # Sanitize and validate input
    try:
        query = sanitize_query(query)
    except ValueError as e:
        log_error(e, "Query validation failed")
        raise
    
    # Validate websites if provided
    if websites:
        validated_websites = validate_websites(websites)
        if not validated_websites:
            print("WARNING: No valid websites provided, using defaults")
            websites = DEFAULT_WEBSITES
        else:
            websites = validated_websites
    else:
        websites = DEFAULT_WEBSITES
    
    print(f"\n{'='*60}")
    print(f"Starting Research: {query}")
    print(f"{'='*60}\n")
    
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
        
        print(f"\n{'='*60}")
        print(f"Research Complete!")
        print(f"{'='*60}")
        print(f"JSON: {result['json_path']}")
        print(f"PDF: {result['pdf_path']}")
        print(f"\nSummary:\n{result['summary'][:200]}...")
        
        return {
            'json_path': result['json_path'],
            'pdf_path': result['pdf_path'],
            'summary': result['summary']
        }
    except Exception as e:
        log_error(e, "Research workflow error")
        raise