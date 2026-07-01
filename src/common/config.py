"""Loads and validates environment configuration shared by all modules."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_REQUIRED_VARS = [
    "ANTHROPIC_API_KEY",
    "NOTION_TOKEN",
    "NOTION_DATA_SOURCE_ID",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
]


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    claude_model: str
    notion_token: str
    notion_data_source_id: str
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    max_emails_per_run: int


def load_config() -> Config:
    missing = [name for name in _REQUIRED_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill in real values, or set them as "
            "GitHub Actions secrets/variables."
        )

    return Config(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"),
        notion_token=os.environ["NOTION_TOKEN"],
        notion_data_source_id=os.environ["NOTION_DATA_SOURCE_ID"],
        google_client_id=os.environ["GOOGLE_CLIENT_ID"],
        google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        google_refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        max_emails_per_run=int(os.environ.get("MAX_EMAILS_PER_RUN", "20")),
    )
