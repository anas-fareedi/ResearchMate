"""
Utility functions for security, validation, and common operations.
"""
import os
import re
import logging
import threading
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
    """Thread-safe rate limiter for HTTP requests."""

    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        # Bug #10 – lock prevents two threads from both passing the interval
        # check simultaneously and defeating the rate limit.
        self._lock = threading.Lock()

    def wait(self):
        """Block the calling thread if needed to honour the rate limit."""
        with self._lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
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
    
    # Limit URL length to prevent DoS attacks
    if len(url) > 2048:
        logger.warning(f"URL exceeds maximum length: {len(url)}")
        return False
    
    url = url.strip()
    
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
        
        # Remove port for validation
        host_only = netloc_lower.split(':')[0]
        
        # Bug #14 – expanded SSRF blocklist:
        #   • Added CGNAT range 100.64.x – 100.127.x (RFC 6598)
        #   • Added IPv6 private/link-local prefixes
        #   • Added metadata service addresses (AWS/GCP/Azure)
        blocked_hosts = [
            'localhost',
            '127.',          # entire 127.0.0.0/8 loopback range
            '0.',            # 0.0.0.0/8
            '::1',
            '[::1]',
            '10.',           # RFC 1918 class-A
            '172.16.',       # RFC 1918 class-B (172.16-31.x)
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
            '192.168.',      # RFC 1918 class-C
            '169.254.',      # Link-local / AWS metadata (169.254.169.254)
            # CGNAT – RFC 6598 (100.64.0.0/10 = 100.64 – 100.127)
            *[f'100.{i}.' for i in range(64, 128)],
            # IPv6 private / link-local / unique-local
            'fc',            # fc00::/7 unique-local
            'fd',
            'fe80',          # fe80::/10 link-local
            # Cloud metadata services
            '169.254.169.254',   # AWS / GCP / Azure IMDS
            'metadata.google.internal',
        ]
        
        for blocked in blocked_hosts:
            if host_only.startswith(blocked) or blocked in host_only:
                logger.warning(f"Blocked private/local URL: {url}")
                return False
        
        # Check for data: URLs and other potentially dangerous schemes hidden in URL
        if 'data:' in url or 'javascript:' in url or 'file:' in url:
            logger.warning(f"Blocked potentially dangerous URL: {url}")
            return False
        
        return True
    
    except ValueError:
        logger.error(f"URL validation error (malformed URL): {url}")
        return False
    except Exception as e:
        logger.error(f"URL validation error for {url}: {type(e).__name__}: {e}")
        return False


def sanitize_query(query: str, max_length: int = 500) -> str:
    """
    Sanitize user query to prevent injection attacks.
    
    Args:
        query: User input query
        max_length: Maximum allowed length
    
    Returns:
        Sanitized query string
        
    Raises:
        ValueError: If query is invalid
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")
    
    # Remove any null bytes and control characters
    query = query.replace('\x00', '')
    # Remove other control characters
    query = ''.join(char for char in query if ord(char) >= 32 or char in '\n\r\t')
    
    # Trim whitespace
    query = query.strip()
    
    # Check length
    if len(query) == 0:
        raise ValueError("Query cannot be empty after sanitization")
    
    if len(query) > max_length:
        logger.warning(f"Query truncated from {len(query)} to {max_length} characters")
        query = query[:max_length].rstrip()  # Remove any trailing incomplete words
    
    # Additional validation - ensure query doesn't contain only special characters
    if not any(char.isalnum() for char in query):
        raise ValueError("Query must contain at least one alphanumeric character")
    
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
