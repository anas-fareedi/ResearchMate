import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from utils import rate_limit
from config import SEARCH_CONFIG

@retry(
    stop=stop_after_attempt(SEARCH_CONFIG.get("max_retries", 3)),
    wait=wait_exponential(multiplier=SEARCH_CONFIG.get("retry_delay", 1), min=1, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError))
)
@rate_limit
def fetch_with_retry(url: str, headers: dict, timeout: int, method: str = 'GET', **kwargs) -> requests.Response:
    """Fetch URL with retry logic and rate limiting."""
    # M5 – never allow callers to disable SSL certificate verification
    kwargs.pop('verify', None)
    response = requests.request(method, url, headers=headers, timeout=timeout, verify=True, **kwargs)
    response.raise_for_status()
    return response
