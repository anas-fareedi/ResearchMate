"""
State definition for the research assistant workflow.
"""
from typing import TypedDict, Annotated, List, Dict
import operator


class ResearchState(TypedDict):
    """
    State for the research assistant workflow.
    
    This state is passed between agents and accumulates information
    as it moves through the workflow pipeline.
    
    Attributes:
        query: The original research query/question
        websites: List of website URLs to search
        search_terms: Key search terms extracted from the query
        urls_found: URLs discovered during search phase
        content: Extracted content from URLs (list of dicts)
        summary: AI-generated summary of the research
        json_path: Path to saved JSON output file
        pdf_path: Path to saved PDF output file
        status: Current workflow status
        messages: Conversation history with LLM (accumulated)
    """
    query: str
    websites: List[str]
    search_terms: List[str]
    urls_found: List[str]
    content: List[Dict]
    summary: str
    json_path: str
    pdf_path: str
    status: str
    messages: Annotated[List, operator.add]  # Track conversation