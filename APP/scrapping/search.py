import sys
import os
from typing import List
import requests
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlencode, quote_plus
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import validate_url, rate_limit, log_error
from config import SEARCH_CONFIG, USER_AGENT, API_CONFIG


@retry(
    stop=stop_after_attempt(SEARCH_CONFIG.get("max_retries", 3)),
    wait=wait_exponential(multiplier=SEARCH_CONFIG.get("retry_delay", 1), min=1, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError))
)
@rate_limit
def _fetch_with_retry(url: str, headers: dict, timeout: int, method: str = 'GET', **kwargs) -> requests.Response:
    """Fetch URL with retry logic and rate limiting."""
    # M5 – never allow callers to disable SSL certificate verification
    kwargs.pop('verify', None)
    response = requests.request(method, url, headers=headers, timeout=timeout, verify=True, **kwargs)
    response.raise_for_status()
    return response


def _clean_discovered_url(raw_url: str) -> str:
    """Normalize noisy URL values returned by external APIs/search pages."""
    if not raw_url:
        return ""

    text = str(raw_url).strip()

    elsevier_match = re.search(
        r"https?://api\.elsevier\.com/content/abstract/scopus_id/\d+",
        text,
        re.IGNORECASE
    )
    if elsevier_match:
        return elsevier_match.group(0)

    url_match = re.search(r"https?://[^\s<>\"]+", text, re.IGNORECASE)
    if not url_match:
        return ""

    return url_match.group(0).rstrip(".,);]")


def search_website(website: str, query: str, max_results: int = 5) -> List[str]:
    """
    Search a website for content related to the query.
    Returns a list of URLs that might contain relevant information.
    
    Args:
        website: Base website URL
        query: Search query
        max_results: Maximum number of URLs to return
    
    Returns:
        List of URLs found
    """
   
    if not validate_url(website):
        log_error(ValueError(f"Invalid website URL: {website}"), "search_website")
        return []
    
    # Special handling for specific sites
    if 'wikipedia.org' in website:
        return get_wikipedia_urls(query)
    elif 'arxiv.org' in website:
        return search_arxiv(query, max_results)
    elif 'semanticscholar.com' in website:
        return search_semantic_scholar(query, max_results)
    elif 'sciencedirect.com' in website or 'scopus.com' in website:
        return search_elsevier(query, max_results)
    
    urls = []
    try:
        # H3 – use urlencode so special chars in the query don't corrupt the URL
        search_url = f"{website}/search?{urlencode({'q': query})}"
        
        headers = {'User-Agent': USER_AGENT}
        timeout = SEARCH_CONFIG.get("request_timeout", 15)
        
        response = _fetch_with_retry(search_url, headers, timeout)
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        for link in links[:max_results * 3]:  
            href = link['href']
            
            # Skip fragment URLs (anchors on same page)
            if href.startswith('#'):
                continue
            
            full_url = urljoin(website, href)
            
            # Remove fragment from URL if present
            parsed = urlparse(full_url)
            full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                full_url += f"?{parsed.query}"
            
            if not validate_url(full_url):
                continue
            
            # Only add URLs from the same domain
            if urlparse(full_url).netloc == urlparse(website).netloc:
                # Skip common non-content URLs and duplicates
                skip_patterns = ['login', 'signup', 'cookie', 'privacy', 'terms', 
                               'about', 'contact', 'help', 'careers', 'faq']
                if not any(skip in full_url.lower() for skip in skip_patterns):
                    if full_url not in urls:  # Avoid duplicates
                        urls.append(full_url)
                        if len(urls) >= max_results:
                            break
        
        print(f"✓ Found {len(urls)} URLs from {website}")
    except Exception as e:
        log_error(e, f"Error searching {website}")
        print(f"✗ Error searching {website}: {str(e)}")
    
    return urls


def search_with_google(query: str, num_results: int = 5) -> List[str]:
    """
    Use Google search to find relevant URLs.
    
    Args:
        query: Search query
        num_results: Number of results to return
    
    Returns:
        List of URLs found
    """
    urls = []
    try:
        # H3 – properly encode query string
        search_url = f"https://www.google.com/search?{urlencode({'q': query})}"
        headers = {'User-Agent': USER_AGENT}
        timeout = SEARCH_CONFIG.get("request_timeout", 15)

        response = _fetch_with_retry(search_url, headers, timeout)

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find search result links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/url?q=' in href:
                # Extract actual URL from Google redirect
                actual_url = href.split('/url?q=')[1].split('&')[0]
                if actual_url.startswith('http') and 'google.com' not in actual_url:
                    if validate_url(actual_url):
                        urls.append(actual_url)
                        if len(urls) >= num_results:
                            break
        print(f"✓ Google search found {len(urls)} URLs")
    except Exception as e:
        log_error(e, "Google search failed")
        print(f"✗ Google search failed: {str(e)}")
    return urls


def search_with_tavily(query: str, num_results: int = 5) -> List[str]:
    """
    Use Tavily API to find relevant URLs.
    Args:
        query: Search query
        num_results: Number of results to return
    Returns:
        List of URLs found
    """
    urls = []
    api_key = API_CONFIG.get("tavily_api_key")

    if not api_key:
        return urls
    try:
        api_url = "https://api.tavily.com/search"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': USER_AGENT,
            # H5 – send API key in Authorization header, not request body
            'Authorization': f'Bearer {api_key}',
        }
        payload = {
            'query': query,
            'search_depth': 'basic',
            'max_results': num_results,
            'include_answer': False,
            'include_raw_content': False
        }

        timeout = SEARCH_CONFIG.get("request_timeout", 15)
        response = _fetch_with_retry(api_url, headers, timeout, method='POST', json=payload)

        data = response.json()
        for item in data.get('results', []):
            url = item.get('url')
            if url and validate_url(url) and url not in urls:
                urls.append(url)
                if len(urls) >= num_results:
                    break

        print(f"✓ Tavily search found {len(urls)} URLs")
    except (requests.RequestException, requests.ConnectionError) as e:
        log_error(e, "Tavily API request failed")
        print(f"✗ Tavily search API error: {str(e)}")
    except ValueError as e:
        log_error(e, "Tavily response parsing error")
        print(f"✗ Tavily response parse error: {str(e)}")
    except Exception as e:
        log_error(e, "Tavily search failed")
        print(f"✗ Tavily search failed: {str(e)}")
    return urls


def get_wikipedia_urls(query: str) -> List[str]:
    """
    Generate Wikipedia URLs for a query.
    Args:
        query: Search query
    Returns:
        List of Wikipedia URLs
    """
    urls = []
    try:
        search_term = query.replace(' ', '_')

        # H3 – encode both URLs properly
        wiki_url = f"https://en.wikipedia.org/wiki/{quote_plus(search_term)}"
        search_url = f"https://en.wikipedia.org/w/index.php?{urlencode({'search': query})}"
        
        headers = {'User-Agent': USER_AGENT}
        timeout = SEARCH_CONFIG.get("request_timeout", 15)
        
        # Check if direct article exists
        response = _fetch_with_retry(wiki_url, headers, timeout)
        if response.status_code == 200 and 'Wikipedia does not have an article' not in response.text:
            urls.append(wiki_url)
            print(f"✓ Found Wikipedia article: {wiki_url}")
        else:
            response = _fetch_with_retry(search_url, headers, timeout)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find search results
            for link in soup.find_all('a', href=True)[:3]:
                href = link['href']
                if href.startswith('/wiki/') and ':' not in href:
                    full_url = urljoin('https://en.wikipedia.org', href)
                    if validate_url(full_url):
                        urls.append(full_url)
            
            print(f"✓ Found {len(urls)} Wikipedia URLs from search")
    except (requests.RequestException, requests.ConnectionError, requests.Timeout) as e:
        log_error(e, "Wikipedia HTTP request failed")
        print(f"✗ Wikipedia request error: {str(e)}")
    except Exception as e:
        log_error(e, "Wikipedia search failed")
        print(f"✗ Wikipedia search failed: {str(e)}")
    return urls


def search_arxiv(query: str, max_results: int = 5) -> List[str]:
    """
    Search ArXiv for research papers using their API.
    Args:
        query: Search query
        max_results: Maximum number of results
    Returns:
        List of ArXiv paper URLs
    """
    urls = []
    try:
        # H4 – use HTTPS; plain HTTP exposes response to MITM interception
        # H3 – use urlencode to safely encode the query term
        api_url = f"https://export.arxiv.org/api/query?{urlencode({'search_query': f'all:{query}', 'start': 0, 'max_results': max_results})}"
        
        headers = {'User-Agent': USER_AGENT}
        timeout = SEARCH_CONFIG.get("request_timeout", 15)
        
        response = _fetch_with_retry(api_url, headers, timeout)
        
        # Use ElementTree for safer XML parsing
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as xml_error:
            log_error(xml_error, "ArXiv XML parse error")
            print(f"✗ Failed to parse ArXiv XML response: {str(xml_error)}")
            return urls
        
        # Extract paper entries - use namespace-aware parsing
        namespace = {'': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('.//entry', namespace) if root.tag.endswith('feed') else root.findall('.//entry')
        
        for entry in entries[:max_results]:
            # Get the paper ID safely
            id_elem = entry.find('id')
            if id_elem is not None and id_elem.text:
                paper_url = id_elem.text.strip()
                # Convert API URL to web URL
                if 'arxiv.org/abs/' in paper_url:
                    urls.append(paper_url)
                elif 'arxiv.org/' in paper_url:
                    # Extract arxiv ID and create proper URL
                    arxiv_id = paper_url.split('/')[-1]
                    if arxiv_id:
                        urls.append(f"https://arxiv.org/abs/{arxiv_id}")
        
        print(f"✓ Found {len(urls)} ArXiv papers")
    except ET.ParseError as e:
        log_error(e, "ArXiv XML parsing failed")
        print(f"✗ ArXiv XML parsing failed: {str(e)}")
    except Exception as e:
        log_error(e, "ArXiv search failed")
        print(f"✗ ArXiv search failed: {str(e)}")
    return urls


def search_semantic_scholar(query: str, max_results: int = 5) -> List[str]:
    """
    Search Semantic Scholar for research papers.
    Uses Semantic Scholar API when key is available.
    Falls back to web scraping if API fails.
    Args:
        query: Search query
        max_results: Maximum number of results
    Returns:
        List of paper URLs
    """
    urls = []


    api_key = API_CONFIG.get("semantic_scholar_api_key")
    if api_key:
        try:
            api_url = "https://api.semanticscholar.org/graph/v1/paper/search"
            headers = {
                'x-api-key': api_key,
                'User-Agent': USER_AGENT
            }
            params = {
                'query': query,
                'limit': max_results,
                'fields': 'paperId,title,url'
            }
            timeout = SEARCH_CONFIG.get("request_timeout", 15)
            response = _fetch_with_retry(api_url, headers, timeout, params=params)

            data = response.json()
            for paper in data.get('data', []):
                paper_url = paper.get('url')
                if not paper_url and paper.get('paperId'):
                    paper_url = f"https://www.semanticscholar.org/paper/{paper['paperId']}"

                if paper_url and validate_url(paper_url) and paper_url not in urls:
                    urls.append(paper_url)
                    if len(urls) >= max_results:
                        break
            print(f"✓ Found {len(urls)} Semantic Scholar papers (API)")
            return urls
        except (requests.RequestException, requests.Timeout) as e:
            log_error(e, "Semantic Scholar API request failed, using web fallback")
        except ValueError as e:
            log_error(e, "Semantic Scholar API response parsing error, using web fallback")

    # Fallback to web search scraping
    try:
        search_url = f"https://www.semanticscholar.org/search?q={query.replace(' ', '+')}&sort=relevance"
        headers = {'User-Agent': USER_AGENT}
        timeout = SEARCH_CONFIG.get("request_timeout", 15)

        response = _fetch_with_retry(search_url, headers, timeout)
        soup = BeautifulSoup(response.content, 'html.parser')

        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/paper/' in href and not href.startswith('#'):
                full_url = urljoin('https://www.semanticscholar.org', href)
                parsed = urlparse(full_url)
                full_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

                if validate_url(full_url) and full_url not in urls:
                    urls.append(full_url)
                    if len(urls) >= max_results:
                        break

        print(f"✓ Found {len(urls)} Semantic Scholar papers")
    except (requests.RequestException, requests.Timeout) as e:
        log_error(e, "Semantic Scholar web search request failed")
        print(f"✗ Semantic Scholar request error: {str(e)}")
    except Exception as e:
        log_error(e, "Semantic Scholar search failed")
        print(f"✗ Semantic Scholar search failed: {str(e)}")
    return urls


def search_elsevier(query: str, max_results: int = 5) -> List[str]:
    """
    Search Elsevier databases (ScienceDirect and Scopus) using the Elsevier API.
    
    Requires Elsevier_API_KEY in environment variables.
    API Documentation: https://dev.elsevier.com/
    Args:
        query: Search query
        max_results: Maximum number of results
    Returns:
        List of ScienceDirect article URLs
    """
    urls = []
    
    api_key = API_CONFIG.get("elsevier_api_key")
    if not api_key:
        print("  Elsevier API key not found. Set Elsevier_API_KEY in .env file")
        print("   Get your key from: https://dev.elsevier.com/")
        return urls
    
    try:
        api_url = "https://api.elsevier.com/content/search/scopus"
        
        headers = {
            'X-ELS-APIKey': api_key,
            'Accept': 'application/json',
            'User-Agent': USER_AGENT
        }
        params = {
            'query': query,
            'count': max_results,
            'field': 'dc:identifier,dc:title,prism:doi,prism:url,eid'
        }
        timeout = SEARCH_CONFIG.get("request_timeout", 15)
        
        response = _fetch_with_retry(
            f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}",
            headers,
            timeout
        )
        data = response.json()
        
        # Extract article URLs from response
        if 'search-results' in data and 'entry' in data['search-results']:
            entries = data['search-results']['entry']
            
            for entry in entries[:max_results]:
                # Try to get ScienceDirect URL
                if 'prism:url' in entry:
                    url = _clean_discovered_url(entry['prism:url'])
                    if validate_url(url):
                        urls.append(url)
                
                # Alternative: construct URL from DOI
                elif 'prism:doi' in entry:
                    doi = entry['prism:doi']
                    doi_url = f"https://doi.org/{doi}"
                    if validate_url(doi_url):
                        urls.append(doi_url)
                
                # Alternative: use Scopus link
                elif 'link' in entry:
                    for link in entry['link']:
                        if link.get('@ref') == 'scopus':
                            scopus_url = _clean_discovered_url(link.get('@href'))
                            if scopus_url and validate_url(scopus_url):
                                urls.append(scopus_url)
                                break
                
                # Fallback: construct Elsevier abstract endpoint from dc:identifier
                elif 'dc:identifier' in entry:
                    identifier = str(entry.get('dc:identifier', ''))
                    id_match = re.search(r"SCOPUS_ID:(\d+)", identifier, re.IGNORECASE)
                    if id_match:
                        abstract_url = f"https://api.elsevier.com/content/abstract/scopus_id/{id_match.group(1)}"
                        if validate_url(abstract_url):
                            urls.append(abstract_url)
        
        print(f"✓ Found {len(urls)} Elsevier/ScienceDirect papers")
        
        if len(urls) == 0:
            print("   Note: Some papers may require institutional access")
        
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 401:
            print("✗ Elsevier API authentication failed. Check your Elsevier_API_KEY")
        elif e.response and e.response.status_code == 429:
            print("✗ Elsevier API rate limit exceeded. Please wait and try again")
        else:
            log_error(e, "Elsevier search failed")
            print(f"✗ Elsevier search failed: HTTP {e.response.status_code if e.response else 'error'}")
    except Exception as e:
        log_error(e, "Elsevier search failed")
        print(f"✗ Elsevier search failed: {str(e)}")
    
    return urls
