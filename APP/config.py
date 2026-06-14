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

    # Supabase Settings
    SUPABASE_URL: str | None = Field(default=None, description="Supabase project URL")
    SUPABASE_KEY: str | None = Field(default=None, description="Supabase API key (anon or service_role)")
    SUPABASE_BUCKET: str = Field(default="ResearchMate", description="Supabase storage bucket name")

    # LangSmith Settings
    LANGCHAIN_TRACING_V2: str = Field(default="false", description="Whether to enable LangChain tracing")
    LANGCHAIN_ENDPOINT: str = Field(default="https://api.smith.langchain.com", description="LangChain API endpoint")
    LANGCHAIN_API_KEY: str | None = Field(default=None, description="LangChain API key")
    LANGCHAIN_PROJECT: str = Field(default="ResearchMate", description="LangChain project name")

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

# Validate LangSmith tracing configuration
if settings.LANGCHAIN_TRACING_V2.lower() == "true":
    if not settings.LANGCHAIN_API_KEY:
        print(
            "WARNING: LangSmith tracing is set to 'true' but LANGCHAIN_API_KEY is not configured.",
            file=sys.stderr,
        )
    else:
        # Explicitly update environment variables so LangChain core detects them
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        print(f"LangSmith tracing enabled - Project: '{settings.LANGCHAIN_PROJECT}'")

# ---------------------------------------------------------------------------
# Legacy dict-style constants kept for backward compat with Agents/document_gen
# ---------------------------------------------------------------------------
API_CONFIG = {
    "gemini_api_key": settings.GEMINI_API_KEY,
    "elsevier_api_key": settings.Elsevier_API_KEY,
    "tavily_api_key": settings.TAVILY_API_KEY,
    "semantic_scholar_api_key": settings.SEMANTIC_SCHOLAR,
    # Jina Reader API key (optional) — raises rate limit from 20 rpm → 200 rpm.
    "jina_api_key": os.getenv("JINA_API_KEY"),
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
    # Number of parallel threads for the extraction phase.
    # Increase for faster extraction; lower if hitting rate limits.
    "extraction_workers": 5,
    # Jina Reader timeout (seconds). Jina itself enforces this server-side.
    # Keep at 10 — requests beyond this fall back to the legacy scraper.
    "jina_timeout": 10,
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
