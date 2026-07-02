"""Discovery-source interface.

Any module that can produce RawStory objects for a lookback window can plug
in here without touching dedup, relevance filtering, generation, or
Notion-writing code -- those all operate on RawStory and never know which
source produced it. See rss.py for the first (and currently only)
implementation; future sources -- Instagram, TikTok, YouTube, Reddit,
Pinterest, newsletters -- implement the same protocol.
"""

import datetime
from typing import Protocol

from src.story_scout.models import RawStory


class Source(Protocol):
    name: str

    def fetch_recent(self, since: datetime.date) -> list[RawStory]: ...
