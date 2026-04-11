from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from utils import validate_url, rate_limit, log_error
from config import SEARCH_CONFIG, USER_AGENT, API_CONFIG
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict
import requests
import sys
import os


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@retry(
    stop=stop_after_attempt(SEARCH_CONFIG.get("max_retries", 3)),
    wait=wait_exponential(multiplier=SEARCH_CONFIG.get("retry_delay", 1), min=1, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError))
)
@rate_limit
def _fetch_with_retry(url: str, headers: dict, timeout: int) -> requests.Response:
    """Fetch URL with retry logic and rate limiting."""
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response


def extract_content(url: str) -> Dict:
    """
    Extract text content from a URL.
    Returns a dictionary with URL, title, and content.
    
    Args:
        url: URL to extract content from
    
    Returns:
        Dictionary with extracted data
    """
    # Validate URL first
    if not validate_url(url):
        log_error(ValueError(f"Invalid URL: {url}"), "extract_content")
        return {
            'url': url,
            'title': 'Error - Invalid URL',
            'content': 'URL validation failed',
            'extracted_at': datetime.now().isoformat()
        }
    try:
        headers = {'User-Agent': USER_AGENT}
        timeout = SEARCH_CONFIG.get("request_timeout", 15)
        response = _fetch_with_retry(url, headers, timeout)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.find('title')
        title_text = title.get_text().strip() if title else "No title"
        
        # Try to find main content 
        content_text = ""
        

        # ArXiv specific extraction
        if 'arxiv.org' in url:
            # Try to get abstract
            abstract_div = soup.find('blockquote', class_='abstract')
            if abstract_div:
                content_text = abstract_div.get_text().strip()
            # Get title from ArXiv specific location
            title_elem = soup.find('h1', class_='title')
            if title_elem:
                title_text = title_elem.get_text().replace('Title:', '').strip()
        

        # Semantic Scholar specific extraction
        elif 'semanticscholar.org' in url:
            # Prefer Semantic Scholar Graph API by paper ID for reliable abstract retrieval.
            paper_id = ""
            if '/paper/' in url:
                paper_part = url.split('/paper/', 1)[1].strip('/')
                if paper_part:
                    paper_id = paper_part.split('/')[-1]
            api_key = API_CONFIG.get("sementic_scholar_api_key")
            if paper_id and api_key:
                try:
                    api_url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
                    api_headers = {
                        'x-api-key': api_key,
                        'User-Agent': USER_AGENT
                    }
                    params = {
                        'fields': 'title,abstract,tldr,url'
                    }
                    api_response = requests.get(api_url, headers=api_headers, params=params, timeout=timeout)
                    api_response.raise_for_status()
                    paper = api_response.json()

                    title_text = paper.get('title') or title_text
                    abstract = (paper.get('abstract') or '').strip()
                    tldr = (paper.get('tldr') or {}).get('text', '').strip()
                    content_text = "\n\n".join([part for part in [abstract, tldr] if part]).strip()
                except Exception as e:
                    log_error(e, f"Semantic Scholar API extraction failed for {paper_id}")

            # Fallback to page scraping when API content is unavailable
            if not content_text:
                abstract_sections = soup.find_all(
                    ['div', 'section'],
                    class_=lambda x: x and ('abstract' in x.lower() or 'tldr' in x.lower())
                )
                for section in abstract_sections:
                    content_text += section.get_text().strip() + "\n\n"
        

        # ScienceDirect/Elsevier specific extraction
        elif 'sciencedirect.com' in url or 'doi.org' in url:
            
            abstract_section = soup.find('div', class_=lambda x: x and 'abstract' in str(x).lower())
            if not abstract_section:
                abstract_section = soup.find('section', {'id': 'abstracts'})
            if not abstract_section:
                abstract_section = soup.find('div', {'id': 'abstracts'})
            
            if abstract_section:
                content_text = abstract_section.get_text().strip()
            

            # Get proper title
            title_elem = soup.find('h1', class_=lambda x: x and 'title' in str(x).lower())
            if not title_elem:
                title_elem = soup.find('span', class_='title-text')
            if title_elem:
                title_text = title_elem.get_text().strip()
        

        # Scopus specific extraction
        elif 'scopus.com' in url:
            abstract_section = soup.find('section', {'id': 'abstractSection'})
            if abstract_section:
                content_text = abstract_section.get_text().strip()
            
            # Scopus title
            title_elem = soup.find('h2', class_='documentTitle')
            if title_elem:
                title_text = title_elem.get_text().strip()
        
        # If no specific extraction worked, use general approach
        if not content_text:
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                script.decompose()
            
            # Try to find main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=lambda x: x and 'content' in str(x).lower())
            
            if main_content:
                text = main_content.get_text()
            else:
                text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content_text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Limit content length
        max_length = SEARCH_CONFIG.get("max_content_length", 5000)
        content_text = content_text[:max_length]
        
        print(f"✓ Extracted content from: {title_text[:60]}")
        return {
            'url': url,
            'title': title_text,
            'content': content_text,
            'extracted_at': datetime.now().isoformat()
        }
    except requests.exceptions.Timeout:
        error_msg = f"Timeout while accessing {url}"
        log_error(TimeoutError(error_msg), "extract_content")
        print(f"✗ {error_msg}")
        return {
            'url': url,
            'title': 'Error - Timeout',
            'content': error_msg,
            'extracted_at': datetime.now().isoformat()
        }
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP error {e.response.status_code if e.response else 'unknown'}"
        log_error(e, f"extract_content - {url}")
        print(f"✗ Error extracting from {url}: {error_msg}")
        return {
            'url': url,
            'title': 'Error - HTTP Error',
            'content': f'Failed to extract: {error_msg}',
            'extracted_at': datetime.now().isoformat()
        }
    except Exception as e:
        log_error(e, f"extract_content - {url}")
        print(f"✗ Error extracting from {url}: {str(e)}")
        return {
            'url': url,
            'title': 'Error',
            'content': f'Failed to extract: {str(e)}',
            'extracted_at': datetime.now().isoformat()
        }