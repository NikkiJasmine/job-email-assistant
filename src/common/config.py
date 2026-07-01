"""Loads and validates environment configuration shared by all modules."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Maps each supported LLM_PROVIDER value to its (api_key env var, model env
# var, default model) triple. Adding a future provider is just one more row
# here plus a matching backend in llm_client.py -- nothing else changes.
_PROVIDER_ENV = {
    "anthropic": ("ANTHROPIC_API_KEY", "CLAUDE_MODEL", "claude-sonnet-5"),
    "openai": ("OPENAI_API_KEY", "OPENAI_MODEL", "gpt-4o-mini"),
    "gemini": ("GEMINI_API_KEY", "GEMINI_MODEL", "gemini-1.5-flash"),
}

_REQUIRED_VARS = [
    "NOTION_TOKEN",
    "NOTION_DATA_SOURCE_ID",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
]


@dataclass(frozen=True)
class Config:
    llm_provider: str
    llm_api_key: str
    llm_model: str
    notion_token: str
    notion_data_source_id: str
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    max_emails_per_run: int


def load_config() -> Config:
    llm_provider = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()
    if llm_provider not in _PROVIDER_ENV:
        raise RuntimeError(
            f"Invalid LLM_PROVIDER '{llm_provider}'. Must be one of: "
            f"{', '.join(_PROVIDER_ENV)}."
        )
    api_key_var, model_var, default_model = _PROVIDER_ENV[llm_provider]

    missing = [name for name in _REQUIRED_VARS if not os.environ.get(name)]
    if not os.environ.get(api_key_var):
        missing.append(api_key_var)
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill in real values, or set them as "
            "GitHub Actions secrets/variables."
        )

    return Config(
        llm_provider=llm_provider,
        llm_api_key=os.environ[api_key_var],
        llm_model=os.environ.get(model_var, default_model),
        notion_token=os.environ["NOTION_TOKEN"],
        notion_data_source_id=os.environ["NOTION_DATA_SOURCE_ID"],
        google_client_id=os.environ["GOOGLE_CLIENT_ID"],
        google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        google_refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        max_emails_per_run=int(os.environ.get("MAX_EMAILS_PER_RUN", "20")),
    )
