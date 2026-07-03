"""Discovery-source interface.

Any module that can produce RawStory objects for a lookback window can plug
in here without touching dedup, scoring, generation, or Notion-writing code
-- those all operate on RawStory and never know which source produced it.
See rss.py, reddit.py, and youtube.py for the current implementations.
Instagram, TikTok, and LinkedIn deliberately do not implement this protocol
(see sources/__init__.py's docstring for why).
"""

import datetime
from typing import Protocol

from src.story_scout.models import RawStory


class Source(Protocol):
    name: str

    def fetch_recent(self, since: datetime.date) -> list[RawStory]: ...
