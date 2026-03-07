import os
import sys

from Agents.agent_state import ResearchState
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from scrapping.search import search_website, search_with_google, get_wikipedia_urls
from scrapping.extract import extract_content
from document_gen import save_to_json, save_to_pdf
from langchain_google_genai import ChatGoogleGenerativeAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import API_CONFIG, LLM_CONFIG, DEFAULT_WEBSITES
from utils import validate_api_key, log_error

# Validate and get API key
GEMINI_API_KEY = validate_api_key(API_CONFIG["gemini_api_key"], "GEMINI_API_KEY")

# Initialize LLM with config
llm = ChatGoogleGenerativeAI(
    model=LLM_CONFIG["model"],
    temperature=LLM_CONFIG["temperature"],
    google_api_key=GEMINI_API_KEY
)

# Agent Nodes

def planning_agent(state: ResearchState) -> ResearchState:
    """
    Analyzes the query and plans the research strategy.
    Extracts key search terms and determines which websites to search.
    """
    query = state['query']
    
    try:
        prompt = f"""You are a research planning assistant. Analyze this research query and extract 3-5 key search terms that would be most effective for finding relevant information.

Query: {query}

Provide ONLY a comma-separated list of search terms, nothing else."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        search_terms = [term.strip() for term in response.content.split(',')]
        
        # Filter out empty terms
        search_terms = [term for term in search_terms if term]
        
        # Use provided websites or default ones
        websites = state.get('websites', DEFAULT_WEBSITES)
        
        print(f"✓ Planning complete. Search terms: {search_terms}")
        print(f"  Websites to search: {', '.join(websites[:3])}{'...' if len(websites) > 3 else ''}")
        
        return {
            **state,
            'search_terms': search_terms,
            'websites': websites,
            'status': 'planned',
            'messages': state.get('messages', []) + [response]
        }
    except Exception as e:
        log_error(e, "planning_agent")
        # Fallback: use the query itself as search term
        return {
            **state,
            'search_terms': [query],
            'websites': state.get('websites', DEFAULT_WEBSITES),
            'status': 'planned',
            'messages': state.get('messages', [])
        }


def search_agent(state: ResearchState) -> ResearchState:
    """
    Searches specified websites for relevant content.
    """
    query = state['query']
    websites = state['websites']
    search_terms = state.get('search_terms', [query])
    
    all_urls = []
    
    try:
        print("\n🔍 Trying Google search...")
        google_urls = search_with_google(query, num_results=5)
        all_urls.extend(google_urls)
    except Exception as e:
        log_error(e, "Google search in search_agent")
    
    print("\n🔍 Searching specified websites...")
    for website in websites:
        try:
            urls = search_website(website, query, max_results=3)
            all_urls.extend(urls)
        except Exception as e:
            log_error(e, f"Website search for {website}")
            continue
    
    # Deduplicate
    all_urls = list(set(all_urls))
    
    # If still no URLs, try Wikipedia directly
    if len(all_urls) == 0:
        print("\n🔍 No URLs found, trying Wikipedia directly...")
        try:
            wiki_urls = get_wikipedia_urls(query)
            all_urls.extend(wiki_urls)
        except Exception as e:
            log_error(e, "Wikipedia fallback search")
    
    print(f"\n✓ Search complete. Found {len(all_urls)} unique URLs")
    
    return {
        **state,
        'urls_found': all_urls,
        'status': 'searched'
    }


def extraction_agent(state: ResearchState) -> ResearchState:
    """
    Extracts content from discovered URLs.
    """
    urls = state['urls_found']
    
    if not urls:
        print("\n⚠️  No URLs to extract from")
        return {
            **state,
            'content': [],
            'status': 'extracted'
        }
    
    from config import SEARCH_CONFIG
    max_urls = SEARCH_CONFIG.get("max_total_urls", 10)
    
    print(f"\n📄 Extracting content from {min(len(urls), max_urls)} URLs...")
    
    content = []
    for i, url in enumerate(urls[:max_urls], 1):
        try:
            print(f"  [{i}/{min(len(urls), max_urls)}] Extracting from: {url[:60]}...")
            extracted = extract_content(url)
            if extracted['content'] and len(extracted['content']) > 100:
                content.append(extracted)
                print(f"      ✓ Extracted {len(extracted['content'])} characters")
            else:
                print(f"      ✗ No content or too short")
        except Exception as e:
            log_error(e, f"extraction_agent - {url}")
            print(f"      ✗ Error: {str(e)[:50]}")
            continue
    
    print(f"\n✓ Extraction complete. Successfully processed {len(content)} pages with content")
    
    return {
        **state,
        'content': content,
        'status': 'extracted'
    }


def summarization_agent(state: ResearchState) -> ResearchState:
    """
    Uses AI to summarize and synthesize the extracted content.
    """
    query = state['query']
    content = state['content']
    
    print(f"\n📝 Generating AI summary from {len(content)} sources...")
    
    # Check if we have content
    if not content or len(content) == 0:
        summary = f"""Unable to extract sufficient content from the searched websites. 

Query: {query}

This could be due to:
- Websites blocking automated access
- Network connectivity issues
- The query being too specific or unusual

Suggestions:
- Try a more general query
- Specify different websites
- Check your internet connection

Note: The research assistant successfully completed all steps but couldn't retrieve enough content to generate a comprehensive summary."""
        print("⚠️  No content available for summarization")
        
        return {
            **state,
            'summary': summary,
            'status': 'summarized',
            'messages': state.get('messages', [])
        }
    
    try:
        # Prepare content for summarization
        from config import SUMMARY_CONFIG
        max_sources = SUMMARY_CONFIG.get("max_sources_to_summarize", 5)
        max_content_per_source = SUMMARY_CONFIG.get("max_content_per_source", 1000)
        
        content_text = "\n\n".join([
            f"Source {i+1}: {item['title']}\nURL: {item['url']}\n{item['content'][:max_content_per_source]}"
            for i, item in enumerate(content[:max_sources])
        ])
        
        summary_length = SUMMARY_CONFIG.get("summary_length", "300-500 words")
        
        prompt = f"""You are a research assistant. Based on the following content extracted from various sources, provide a comprehensive summary that answers this research query.

Query: {query}

Extracted Content from {len(content)} sources:

{content_text}

Provide a well-structured summary ({summary_length}) that:
1. Directly answers the research query
2. Synthesizes information from multiple sources
3. Highlights key findings and insights
4. Is clear and informative

Summary:"""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        summary = response.content
        print(f"✓ Summarization complete ({len(summary)} characters)")
        
        return {
            **state,
            'summary': summary,
            'status': 'summarized',
            'messages': state.get('messages', []) + [response]
        }
    except Exception as e:
        log_error(e, "summarization_agent")
        # Fallback: create a basic summary
        summary = f"Research query: {query}\n\nFound {len(content)} sources but encountered an error during summarization. Please check the extracted content in the output files."
        return {
            **state,
            'summary': summary,
            'status': 'summarized',
            'messages': state.get('messages', [])
        }


def saving_agent(state: ResearchState) -> ResearchState:
    """
    Saves the research results to JSON and PDF files.
    """
    query = state['query']
    content = state['content']
    summary = state['summary']
    
    data = {
        'query': query,
        'search_terms': state.get('search_terms', []),
        'websites_searched': state['websites'],
        'urls_found': state['urls_found'],
        'content': content,
        'summary': summary
    }
    
    json_path = ""
    pdf_path = ""
    
    try:
        json_path = save_to_json(data, query)
    except Exception as e:
        log_error(e, "saving_agent - JSON save failed")
        print(f"✗ Failed to save JSON: {str(e)}")
    
    try:
        pdf_path = save_to_pdf(data, query, summary)
    except Exception as e:
        log_error(e, "saving_agent - PDF save failed")
        print(f"✗ Failed to save PDF: {str(e)}")
    
    if json_path and pdf_path:
        print(f"✓ All files saved successfully")
    elif json_path or pdf_path:
        print(f"⚠️  Partial save: Some files could not be saved")
    else:
        print(f"✗ Failed to save output files")
    
    return {
        **state,
        'json_path': json_path,
        'pdf_path': pdf_path,
        'status': 'completed'
    }