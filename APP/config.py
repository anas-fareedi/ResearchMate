import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# Load .env from the project root (one level above APP/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Settings(BaseSettings):
    # App Settings
    ENVIRONMENT: str = Field(default="development", description="development or production")
    CORS_ALLOW_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    API_ACCESS_TOKEN: str | None = Field(default=None, description="Optional shared token for API access")

    # API Keys
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")
    Elsevier_API_KEY: str | None = Field(default=None)
    TAVILY_API_KEY: str | None = Field(default=None)
    SEMANTIC_SCHOLAR: str | None = Field(default=None)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Validate required keys early with a clear human-readable error
if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("your-"):
    print(
        "\nERROR: GEMINI_API_KEY is not configured.\n"
        "  1. Open the .env file in the project root\n"
        "  2. Set GEMINI_API_KEY=<your real key>\n"
        "  Get a key at: https://makersuite.google.com/app/apikey\n",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Legacy dict-style constants kept for backward compat with Agents/document_gen
# ---------------------------------------------------------------------------
API_CONFIG = {
    "gemini_api_key": settings.GEMINI_API_KEY,
    "elsevier_api_key": settings.Elsevier_API_KEY,
    "tavily_api_key": settings.TAVILY_API_KEY,
    "semantic_scholar_api_key": settings.SEMANTIC_SCHOLAR,
}

LLM_CONFIG = {
    "model": "gemini-2.5-flash-lite",
    "temperature": 0.3,
    "max_tokens": 1024,
}

SEARCH_CONFIG = {
    "max_urls_per_website": 3,
    "max_total_urls": 10,
    "request_timeout": 15,
    "max_content_length": 5000,
    "max_retries": 3,
    "retry_delay": 1,
}

DEFAULT_WEBSITES = [
    "https://scholar.google.com",
    "https://www.researchgate.net",
    "https://arxiv.org",
    "https://www.sciencedirect.com",
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
    "max_sources_to_summarize": 3,
    "max_content_per_source": 700,
    "summary_length": "180-250 words",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)

WEBSITE_RULES = {
    "wikipedia.org": {
        "content_selector": "#mw-content-text",
        "remove_elements": ["#toc", ".navbox"],
    },
}

RATE_LIMIT = {
    "enabled": True,
    "requests_per_second": 1,
    "delay_between_requests": 1,
}
