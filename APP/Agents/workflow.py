"""
LangGraph workflow for research assistant.
"""
from Agents.agent_state import ResearchState
from langgraph.graph import StateGraph, START, END
from Agents.Agents import planning_agent, search_agent, extraction_agent, summarization_agent, saving_agent


def build_research_workflow():
    """
    Build the LangGraph workflow for research assistant.
    
    Creates a sequential workflow with the following stages:
    1. Planning - Analyze query and extract search terms
    2. Searching - Find relevant URLs from websites
    3. Extraction - Extract content from URLs
    4. Summarization - Generate AI summary from content
    5. Saving - Save results to JSON and PDF
    
    Returns:
        Compiled LangGraph workflow application
    """
    workflow = StateGraph(ResearchState)
    
    # Add agent nodes
    workflow.add_node("planning", planning_agent)
    workflow.add_node("searching", search_agent)
    workflow.add_node("extraction", extraction_agent)
    workflow.add_node("summarization", summarization_agent)
    workflow.add_node("saving", saving_agent)
    
    # Define workflow edges (sequential execution)
    workflow.add_edge(START, "planning")
    workflow.add_edge("planning", "searching")
    workflow.add_edge("searching", "extraction")
    workflow.add_edge("extraction", "summarization")
    workflow.add_edge("summarization", "saving")
    workflow.add_edge("saving", END)
    
    # Compile and return the workflow
    app = workflow.compile()
    
    return app
