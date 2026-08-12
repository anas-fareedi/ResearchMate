import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure parent directory is on the path before any local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agents.agent_state import ResearchState
from langchain_core.messages import HumanMessage
from scrapping.search import search_website, search_with_google, search_with_tavily, search_semantic_scholar, get_wikipedia_urls
from scrapping.extract import extract_content
from document_gen import save_to_json, save_to_pdf
from langchain_google_genai import ChatGoogleGenerativeAI
from config import API_CONFIG, LLM_CONFIG, DEFAULT_WEBSITES, SEARCH_CONFIG, SUMMARY_CONFIG
from utils import validate_api_key, log_error, logger, update_celery_progress

_llm = None  # lazy singleton — created on first use


def _get_llm():
    """Return (and lazily create) the shared Gemini LLM client."""
    global _llm
    if _llm is None:
        gemini_api_key = validate_api_key(API_CONFIG["gemini_api_key"], "GEMINI_API_KEY")
        _llm = ChatGoogleGenerativeAI(
            model=LLM_CONFIG["model"],
            temperature=LLM_CONFIG["temperature"],
            max_output_tokens=LLM_CONFIG["max_tokens"],
            google_api_key=gemini_api_key,
        )
    return _llm


# Agent Nodes

def planning_agent(state: ResearchState) -> ResearchState:
    """
    Analyzes the query and plans the research strategy.
    Extracts key search terms and determines which websites to search.
    """
    update_celery_progress("planning", "Planning Research...", 10)
    query = state['query']
    
    try:
        # M2 – wrap user content in delimiters so injected instructions
        #       cannot blend with the system prompt text.
        prompt = (
            "Extract 3-5 key search terms for the research query below. "
            "Return only comma-separated terms.\n"
            'Query: """\n'
            f"{query}\n"
            '"""'
        )
        
        response = _get_llm().invoke([HumanMessage(content=prompt)])
        search_terms = [term.strip() for term in response.content.split(',')]
        
        # Filter out empty terms
        search_terms = [term for term in search_terms if term]
        
        websites = state.get('websites', DEFAULT_WEBSITES)
        
        logger.info(f"Planning complete. Search terms: {search_terms}")
        logger.info(f"Websites to search: {', '.join(websites[:3])}{'...' if len(websites) > 3 else ''}")
        
        return {
            **state,
            'search_terms': search_terms,
            'websites': websites,
            'status': 'planned',
            'messages': state.get('messages', []) + [response]
        }
    except Exception as e:
        log_error(e, "planning_agent")
        return {
            **state,
            'search_terms': [query],
            'websites': state.get('websites', DEFAULT_WEBSITES),
            'status': 'planned',
            'messages': state.get('messages', [])
        }


def search_agent(state: ResearchState) -> ResearchState:
    """
    Searches specified websites for relevant content in parallel.
    All search providers (Tavily, Google, Semantic Scholar, per-website)
    are fired concurrently and their results merged.
    """
    update_celery_progress("searching", "Searching Sources...", 30)
    query = state['query']
    websites = state['websites']

    # Build list of (label, callable) search tasks
    search_tasks = [
        ("Tavily",           lambda: search_with_tavily(query, num_results=5)),
        ("Google",           lambda: search_with_google(query, num_results=5)),
        ("Semantic Scholar", lambda: search_semantic_scholar(query, max_results=5)),
    ]
    for website in websites:
        # Capture website in default-arg to avoid late-binding closure issues
        search_tasks.append(
            (f"Website:{website}", lambda w=website: search_website(w, query, max_results=3))
        )

    all_urls = []
    logger.info(f"Running {len(search_tasks)} search tasks in parallel...")

    with ThreadPoolExecutor(max_workers=len(search_tasks)) as executor:
        future_to_label = {
            executor.submit(fn): label for label, fn in search_tasks
        }
        for future in as_completed(future_to_label):
            label = future_to_label[future]
            try:
                urls = future.result()
                all_urls.extend(urls)
                logger.info(f"{label} returned {len(urls)} URLs")
            except Exception as e:
                log_error(e, f"{label} search in search_agent")

    all_urls = list(set(all_urls))

    if len(all_urls) == 0:
        logger.warning("No URLs found from search providers, trying Wikipedia directly...")
        try:
            wiki_urls = get_wikipedia_urls(query)
            all_urls.extend(wiki_urls)
        except Exception as e:
            log_error(e, "Wikipedia fallback search")

    logger.info(f"Search complete. Found {len(all_urls)} unique URLs")

    return {
        **state,
        'urls_found': all_urls,
        'status': 'searched'
    }


def extraction_agent(state: ResearchState) -> ResearchState:
    """
    Extracts content from discovered URLs in parallel.
    Uses a bounded thread pool so we don't hammer target servers.
    """
    update_celery_progress("extracting", "Extracting Content...", 50)
    urls = state['urls_found']

    if not urls:
        logger.warning("No URLs to extract from")
        return {
            **state,
            'content': [],
            'status': 'extracted'
        }

    max_urls = SEARCH_CONFIG.get("max_total_urls", 10)
    # Cap parallel workers: enough to be fast, not so many we get rate-limited
    max_workers = min(SEARCH_CONFIG.get("extraction_workers", 5), max_urls)
    urls_to_process = urls[:max_urls]

    logger.info(
        f"Extracting content from {len(urls_to_process)} URLs "
        f"using {max_workers} parallel workers..."
    )

    # Use a dict to preserve insertion order after futures complete
    results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(extract_content, url): url
            for url in urls_to_process
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                extracted = future.result()
                if extracted['content'] and len(extracted['content']) > 100:
                    results[url] = extracted
                    logger.debug(f"Extracted {len(extracted['content'])} chars from {url[:80]}")
                else:
                    logger.debug(f"Skipped (too short): {url[:80]}")
            except Exception as e:
                log_error(e, f"extraction_agent - {url}")
                logger.warning(f"Error extracting from URL: {str(e)[:80]}")

    # Restore original URL order so summarization sees a consistent ordering
    content = [results[url] for url in urls_to_process if url in results]

    logger.info(f"Extraction complete. Successfully processed {len(content)} pages")

    return {
        **state,
        'content': content,
        'status': 'extracted'
    }


def summarization_agent(state: ResearchState) -> ResearchState:
    """
    Uses AI to summarize and synthesize the extracted content.
    """
    update_celery_progress("summarizing", "Generating Report...", 70)
    query = state['query']
    content = state['content']
    
    logger.info(f"Generating AI summary from {len(content)} sources...")
    
    if not content or len(content) == 0:
        summary = f"""Unable to extract sufficient content from the searched websites. 

Query: {query}
This could be due to:
- Websites blocking automated access
- Network connectivity issues

Suggestions:
- Try a more general query
- Specify different websites

Note: The research assistant successfully completed all steps but couldn't retrieve enough content to generate a comprehensive summary."""
        logger.warning("No content available for summarization")
        
        return {
            **state,
            'summary': summary,
            'status': 'summarized',
            'messages': state.get('messages', [])
        }
    
    # Prepare content for summarization
    try:
        max_sources = SUMMARY_CONFIG.get("max_sources_to_summarize", 5)
        max_content_per_source = SUMMARY_CONFIG.get("max_content_per_source", 1000)
        
        content_text = "\n\n".join([
            f"Source {i+1}: {item['title']}\nURL: {item['url']}\n{item['content'][:max_content_per_source]}"
            for i, item in enumerate(content[:max_sources])
        ])
        summary_length = SUMMARY_CONFIG.get("summary_length", "300-500 words")
        
        # M2 – delimit user query and source content to resist prompt injection
        prompt = (
            f"Summarize the content to answer the query in {summary_length}. "
            "Synthesize across sources and include key findings.\n"
            'Query: """\n'
            f"{query}\n"
            '"""\n\n'
            f"Sources:\n{content_text}"
        )
        response = _get_llm().invoke([HumanMessage(content=prompt)])
        summary = response.content
        logger.info(f"Summarization complete ({len(summary)} characters)")
        
        return {
            **state,
            'summary': summary,
            'status': 'summarized',
            'messages': state.get('messages', []) + [response]
        }
    except Exception as e:
        log_error(e, "summarization_agent")
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
    update_celery_progress("saving", "Creating PDF...", 90)
    from datetime import datetime as _dt

    query = state['query']
    content = state['content']
    summary = state['summary']

    # ── Build citations list ───────────────────────────────────────────────
    # Each citation is a numbered reference entry that will appear in both
    # the PDF References section and the returned API payload.
    access_date = _dt.utcnow().strftime("%Y-%m-%d")
    citations = []
    for i, item in enumerate(content, start=1):
        url = (item.get('url') or '').strip()
        title = (item.get('title') or url or f'Source {i}').strip()
        if not url:
            continue
        citations.append({
            'number': i,
            'title': title,
            'url': url,
            'accessed': access_date,
        })

    data = {
        'query': query,
        'search_terms': state.get('search_terms', []),
        'websites_searched': state['websites'],
        'urls_found': state['urls_found'],
        'content': content,
        'summary': summary,
        'citations': citations,
    }

    json_path = ""
    pdf_path = ""

    try:
        json_path = save_to_json(data, query)
    except Exception as e:
        log_error(e, "saving_agent - JSON save failed")
        logger.error(f"Failed to save JSON: {e}")

    try:
        pdf_path = save_to_pdf(data, query, summary)
    except Exception as e:
        log_error(e, "saving_agent - PDF save failed")
        logger.error(f"Failed to save PDF: {e}")

    if json_path and pdf_path:
        logger.info("All output files saved successfully")
    elif json_path or pdf_path:
        logger.warning("Partial save: some output files could not be saved")
    else:
        logger.error("Failed to save all output files")

    return {
        **state,
        'json_path': json_path,
        'pdf_path': pdf_path,
        'status': 'completed'
    }
