from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from utils import validate_url, rate_limit, log_error
from config import SEARCH_CONFIG, USER_AGENT, API_CONFIG
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict
import requests
import re
import json
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


def _normalize_input_url(url: str) -> str:
    """Extract a valid URL when extra metadata is concatenated to it."""
    if not url:
        return ""
    text = str(url).strip()

    elsevier_match = re.search(
        r"https?://api\.elsevier\.com/content/abstract/scopus_id/\d+",
        text,
        re.IGNORECASE
    )
    if elsevier_match:
        return elsevier_match.group(0)

    generic_match = re.search(r"https?://[^\s<>\"]+", text, re.IGNORECASE)
    if not generic_match:
        return ""
    return generic_match.group(0).rstrip(".,);]")


def _first_text_value(obj, candidate_keys) -> str:
    """Find the first non-empty string value for any candidate key in nested JSON."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in candidate_keys and isinstance(value, str) and value.strip():
                return value.strip()
            found = _first_text_value(value, candidate_keys)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _first_text_value(item, candidate_keys)
            if found:
                return found
    return ""


def extract_content(url: str) -> Dict:
    """
    Extract text content from a URL.
    Returns a dictionary with URL, title, and content.
    
    Args:
        url: URL to extract content from
    
    Returns:
        Dictionary with extracted data
    """
    normalized_url = _normalize_input_url(url)
    if not normalized_url:
        normalized_url = url

    # Validate URL first
    if not validate_url(normalized_url):
        log_error(ValueError(f"Invalid URL: {url}"), "extract_content")
        return {
            'url': normalized_url,
            'title': 'Error - Invalid URL',
            'content': 'URL validation failed',
            'extracted_at': datetime.now().isoformat()
        }
    try:
        headers = {'User-Agent': USER_AGENT}
        timeout = SEARCH_CONFIG.get("request_timeout", 15)

        if "api.elsevier.com/content/abstract/scopus_id/" in normalized_url:
            api_key = API_CONFIG.get("elsevier_api_key")
            if api_key:
                headers['X-ELS-APIKey'] = api_key
            headers['Accept'] = 'application/json'

        response = _fetch_with_retry(normalized_url, headers, timeout)

        if "api.elsevier.com/content/abstract/scopus_id/" in normalized_url:
            data = response.json()
            root = data.get('abstracts-retrieval-response', {})
            core = root.get('coredata', {})
            scopus_match = re.search(r"scopus_id/(\d+)", normalized_url, re.IGNORECASE)
            fallback_title = f"Scopus ID {scopus_match.group(1)}" if scopus_match else "Elsevier Abstract"

            title_text = (
                core.get('dc:title')
                or core.get('dc:description')
                or core.get('prism:publicationName')
                or fallback_title
            )

            content_text = (
                core.get('dc:description')
                or _first_text_value(root, {'dc:description', 'abstract', 'ce:para'})
            )
            if not content_text:
                content_text = json.dumps(core, ensure_ascii=False)

            max_length = SEARCH_CONFIG.get("max_content_length", 5000)
            content_text = content_text[:max_length]

            print(f"✓ Extracted content from: {title_text[:60]}")
            return {
                'url': normalized_url,
                'title': title_text,
                'content': content_text,
                'extracted_at': datetime.now().isoformat()
            }

        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.find('title')
        title_text = title.get_text().strip() if title else "No title"
        
        # Try to find main content 
        content_text = ""
        

        # ArXiv specific extraction
        if 'arxiv.org' in normalized_url:
            # Try to get abstract
            abstract_div = soup.find('blockquote', class_='abstract')
            if abstract_div:
                content_text = abstract_div.get_text().strip()
            # Get title from ArXiv specific location
            title_elem = soup.find('h1', class_='title')
            if title_elem:
                title_text = title_elem.get_text().replace('Title:', '').strip()
        

        # Semantic Scholar specific extraction
        elif 'semanticscholar.org' in normalized_url:
            # Prefer Semantic Scholar Graph API by paper ID for reliable abstract retrieval.
            paper_id = ""
            if '/paper/' in normalized_url:
                paper_part = normalized_url.split('/paper/', 1)[1].strip('/')
                if paper_part:
                    paper_id = paper_part.split('/')[-1]
            api_key = API_CONFIG.get("semantic_scholar_api_key")
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
        elif 'sciencedirect.com' in normalized_url or 'doi.org' in normalized_url or 'api.elsevier.com' in normalized_url:
            
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
        elif 'scopus.com' in normalized_url:
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
            'url': normalized_url,
            'title': title_text,
            'content': content_text,
            'extracted_at': datetime.now().isoformat()
        }
    except requests.exceptions.Timeout:
        error_msg = f"Timeout while accessing {normalized_url}"
        log_error(TimeoutError(error_msg), "extract_content")
        print(f"✗ {error_msg}")
        return {
            'url': normalized_url,
            'title': 'Error - Timeout',
            'content': error_msg,
            'extracted_at': datetime.now().isoformat()
        }
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP error {e.response.status_code if e.response else 'unknown'}"
        log_error(e, f"extract_content - {normalized_url}")
        print(f"✗ Error extracting from {normalized_url}: {error_msg}")
        return {
            'url': normalized_url,
            'title': 'Error - HTTP Error',
            'content': f'Failed to extract: {error_msg}',
            'extracted_at': datetime.now().isoformat()
        }
    except Exception as e:
        log_error(e, f"extract_content - {normalized_url}")
        print(f"✗ Error extracting from {normalized_url}: {str(e)}")
        return {
            'url': normalized_url,
            'title': 'Error',
            'content': f'Failed to extract: {str(e)}',
            'extracted_at': datetime.now().isoformat()
        }
