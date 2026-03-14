import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
API_CONFIG = {
    "gemini_api_key": os.getenv("GEMINI_API_KEY"),
    "elsevier_api_key": os.getenv("Elsevier_API_KEY"),
    "tavily_api_key": os.getenv("TAVILY_API_KEY"),
    "sementic_scholar_api_key": os.getenv("SEMENTIC_SCHOLAR") or os.getenv("SEMANTIC_SCHOLAR"),
}

LLM_CONFIG = {
    "model": "gemini-2.5-flash",  
    "temperature": 0.3,  
    "max_tokens": 2048
}

SEARCH_CONFIG = {
    "max_urls_per_website": 3,  # How many URLs to extract from each website
    "max_total_urls": 10,  # Maximum total URLs to process
    "request_timeout": 15,  # Timeout for HTTP requests in seconds
    "max_content_length": 5000,  # Maximum characters to extract from each page
    "max_retries": 3,  # Maximum retry attempts for failed requests
    "retry_delay": 1,  # Delay between retries in seconds
}

DEFAULT_WEBSITES = [
    # General Knowledge
    # "https://en.wikipedia.org",
    
    # Academic & Research
    "https://scholar.google.com",
    "https://www.researchgate.net",
    "https://arxiv.org",
    # "https://pubmed.ncbi.nlm.nih.gov",
    
    # Scientific Journals
    # "https://www.nature.com",
    "https://www.sciencedirect.com",
    # "https://www.science.org",
    
    # Technology
    # "https://techcrunch.com",
    # "https://www.wired.com",
    # "https://arstechnica.com",
]

OUTPUT_CONFIG = {
    "directory": "research_outputs",
    "json_indent": 2,
    "pdf_font": "Arial",
    "pdf_font_size": 11,
    "include_metadata": True,
    "save_json": True,
    "save_pdf": True,
}

SUMMARY_CONFIG = {
    "max_sources_to_summarize": 5,  # Number of sources to include in summary
    "max_content_per_source": 1000,  # Characters per source for summarization
    "summary_length": "300-500 words",  # Target summary length
}

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'


WEBSITE_RULES = {
    "wikipedia.org": {
        "content_selector": "#mw-content-text",  # CSS selector for main content
        "remove_elements": ["#toc", ".navbox"]  # Elements to remove
    },
    # Add more website-specific rules as needed
}
RATE_LIMIT = {
    "enabled": True,
    "requests_per_second": 1,  # Maximum requests per second
    "delay_between_requests": 1  # Seconds to wait between requests
}