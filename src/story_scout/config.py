"""Loads and validates environment configuration for the Story Scout AI module.

Deliberately independent from src/common/config.py's load_config(), which is
wired specifically to the Job Email Assistant's own database id
(NOTION_DATA_SOURCE_ID for the job-search CRM). Story Scout uses a different
Notion database, so it needs its own id var -- but it reuses the same Google
OAuth credentials (to send its notification email) since both modules share
one Gmail account and one OAuth consent grant.

REDDIT_CLIENT_ID/SECRET and YOUTUBE_API_KEY are optional: those sources are
skipped (not a hard failure) when unset, so the pipeline runs on RSS alone
until you add them -- see sources/__init__.py.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_REQUIRED_VARS = [
    "ANTHROPIC_API_KEY",
    "NOTION_TOKEN",
    "NOTION_STORY_DATABASE_ID",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
    "STORY_SCOUT_NOTIFY_EMAIL",
]


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    claude_model: str
    notion_token: str
    notion_story_database_id: str
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    notify_email: str
    recipient_name: str
    lookback_days: int
    top_n: int
    reddit_client_id: str
    reddit_client_secret: str
    youtube_api_key: str


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
        google_client_id=os.environ["GOOGLE_CLIENT_ID"],
        google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        google_refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        notify_email=os.environ["STORY_SCOUT_NOTIFY_EMAIL"],
        recipient_name=os.environ.get("STORY_SCOUT_RECIPIENT_NAME", "you"),
        # Every-3-days run with a 1-day buffer so a delayed/failed run doesn't create a gap.
        lookback_days=int(os.environ.get("STORY_SCOUT_LOOKBACK_DAYS", "4")),
        top_n=int(os.environ.get("STORY_SCOUT_TOP_N", "5")),
        reddit_client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
        reddit_client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
        youtube_api_key=os.environ.get("YOUTUBE_API_KEY", ""),
    )
