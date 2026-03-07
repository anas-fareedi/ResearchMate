# Scrapping module for web searching and content extraction
from .search import search_website, search_with_google, get_wikipedia_urls
from .extract import extract_content

__all__ = ['search_website', 'search_with_google', 'get_wikipedia_urls', 'extract_content']