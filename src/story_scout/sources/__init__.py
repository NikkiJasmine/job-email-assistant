"""Assembles the list of enabled discovery sources for a Story Scout run.

Currently just the curated RSS feed list. Future non-RSS sources (Instagram,
TikTok, YouTube, Reddit, Pinterest, newsletters -- see base.py's Source
protocol) get added here without any other pipeline code changing.
"""

from src.story_scout.sources.base import Source
from src.story_scout.sources.feeds import TRUSTED_RSS_FEEDS
from src.story_scout.sources.rss import RSSSource


def get_enabled_sources() -> list[Source]:
    return [RSSSource(name, category, url) for name, category, url in TRUSTED_RSS_FEEDS]
