"""
Utility functions for security, validation, and common operations.
"""
import os
import re
import logging
from typing import Optional, List
from urllib.parse import urlparse
import time
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter for HTTP requests."""
    
    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0
    
    def wait(self):
        """Wait if necessary to respect rate limit."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_interval:
            sleep_time = self.min_interval - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()


# Global rate limiter instance
_rate_limiter = RateLimiter(requests_per_second=2.0)


def rate_limit(func):
    """Decorator to apply rate limiting to functions."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        _rate_limiter.wait()
        return func(*args, **kwargs)
    return wrapper


def validate_api_key(api_key: Optional[str], key_name: str = "API_KEY") -> str:
    """
    Validate that an API key is present and not empty.
    
    Args:
        api_key: The API key to validate
        key_name: Name of the key for error messages
    
    Returns:
        The validated API key
    
    Raises:
        ValueError: If API key is missing or invalid
    """
    if not api_key:
        raise ValueError(
            f"{key_name} is not set. Please set it in your .env file:\n"
            f"{key_name}=your_api_key_here"
        )
    
    if len(api_key.strip()) < 10:
        raise ValueError(f"{key_name} appears to be invalid (too short)")
    
    return api_key.strip()


def validate_url(url: str) -> bool:
    """
    Validate URL to prevent SSRF and other injection attacks.
    
    Args:
        url: URL to validate
    
    Returns:
        True if URL is valid and safe, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    try:
        parsed = urlparse(url)
        
        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Only allow http and https
        if parsed.scheme not in ['http', 'https']:
            logger.warning(f"Invalid URL scheme: {parsed.scheme}")
            return False
        
        # Prevent localhost/private IP access (SSRF protection)
        netloc_lower = parsed.netloc.lower()
        blocked_hosts = [
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            '::1',
            '10.',
            '172.16.',
            '172.17.',
            '172.18.',
            '172.19.',
            '172.20.',
            '172.21.',
            '172.22.',
            '172.23.',
            '172.24.',
            '172.25.',
            '172.26.',
            '172.27.',
            '172.28.',
            '172.29.',
            '172.30.',
            '172.31.',
            '192.168.',
        ]
        
        for blocked in blocked_hosts:
            if netloc_lower.startswith(blocked) or blocked in netloc_lower:
                logger.warning(f"Blocked private/local URL: {url}")
                return False
        
        return True
    
    except Exception as e:
        logger.error(f"URL validation error for {url}: {e}")
        return False


def sanitize_query(query: str, max_length: int = 500) -> str:
    """
    Sanitize user query to prevent injection attacks.
    
    Args:
        query: User input query
        max_length: Maximum allowed length
    
    Returns:
        Sanitized query string
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")
    
    # Remove any null bytes
    query = query.replace('\x00', '')
    
    # Trim whitespace
    query = query.strip()
    
    # Check length
    if len(query) == 0:
        raise ValueError("Query cannot be empty")
    
    if len(query) > max_length:
        logger.warning(f"Query truncated from {len(query)} to {max_length} characters")
        query = query[:max_length]
    
    return query


def validate_websites(websites: List[str]) -> List[str]:
    """
    Validate a list of website URLs.
    
    Args:
        websites: List of website URLs
    
    Returns:
        List of validated URLs (invalid ones are filtered out)
    """
    if not websites:
        return []
    
    valid_websites = []
    for url in websites:
        if validate_url(url):
            valid_websites.append(url)
        else:
            logger.warning(f"Skipping invalid website URL: {url}")
    
    return valid_websites


def ensure_output_directory(directory: str) -> str:
    """
    Ensure output directory exists, create if it doesn't.
    
    Args:
        directory: Path to directory
    
    Returns:
        Absolute path to directory
    """
    abs_dir = os.path.abspath(directory)
    os.makedirs(abs_dir, exist_ok=True)
    return abs_dir


def log_error(error: Exception, context: str = ""):
    """
    Log an error with context.
    
    Args:
        error: The exception to log
        context: Additional context about where the error occurred
    """
    if context:
        logger.error(f"{context}: {type(error).__name__}: {str(error)}")
    else:
        logger.error(f"{type(error).__name__}: {str(error)}")
