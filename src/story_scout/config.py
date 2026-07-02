"""Loads and validates environment configuration for the Story Scout AI module.

Deliberately independent from src/common/config.py's load_config(), which is
wired specifically to the Job Email Assistant (Gmail/Google credentials,
NOTION_DATA_SOURCE_ID for the job-search CRM database). Story Scout needs
neither Gmail credentials nor that database id, and adding its vars to the
shared loader would force unrelated env vars onto both modules.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_REQUIRED_VARS = [
    "ANTHROPIC_API_KEY",
    "NOTION_TOKEN",
    "NOTION_STORY_DATABASE_ID",
]


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    claude_model: str
    notion_token: str
    notion_story_database_id: str
    lookback_days: int


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
        notion_story_database_id=os.environ["NOTION_STORY_DATABASE_ID"],
        # Daily run with a 1-day buffer so a delayed/failed run doesn't create a gap.
        lookback_days=int(os.environ.get("STORY_SCOUT_LOOKBACK_DAYS", "2")),
    )
