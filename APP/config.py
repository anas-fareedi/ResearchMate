import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# Load .env from the project root (one level above APP/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class Settings(BaseSettings):
    # App Settings
    ENVIRONMENT: str = Field(default="development", description="development or production")
    CORS_ALLOW_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    # API Keys
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API Key")
    Elsevier_API_KEY: str | None = Field(default=None)
    TAVILY_API_KEY: str | None = Field(default=None)
    SEMANTIC_SCHOLAR: str | None = Field(default=None)

    # Firebase
    FIREBASE_PROJECT_ID: str | None = Field(default=None)
    FIREBASE_STORAGE_BUCKET: str | None = Field(default=None)
    FIREBASE_SERVICE_ACCOUNT_PATH: str | None = Field(default=None)
    FIREBASE_SERVICE_ACCOUNT_JSON: str | None = Field(default=None)
    FIREBASE_DATABASE_URL: str | None = Field(default=None)
    db_url: str | None = Field(default=None)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

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

