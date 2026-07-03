"""RSS/Atom implementation of the Source protocol."""

import datetime
import logging

import feedparser

from src.story_scout.models import RawStory

logger = logging.getLogger("story_scout.sources.rss")

_MAX_ENTRIES_PER_FEED = 30


class RSSSource:
    def __init__(self, name: str, feed_url: str):
        self.name = name
        self.feed_url = feed_url

    def fetch_recent(self, since: datetime.date) -> list[RawStory]:
        parsed = feedparser.parse(self.feed_url)
        if parsed.bozo and not parsed.entries:
            logger.warning(
                "Feed %r (%s) failed to parse: %s", self.name, self.feed_url, parsed.get("bozo_exception")
            )
            return []

        stories = []
        for entry in parsed.entries[:_MAX_ENTRIES_PER_FEED]:
            published = _entry_date(entry)
            if published is not None and published < since:
                continue
            url = entry.get("link")
            title = entry.get("title")
            if not url or not title:
                continue
            summary = entry.get("summary", "")
            stories.append(
                RawStory(
                    source_name=self.name,
                    platform="RSS",
                    title=title,
                    url=url,
                    published_at=published,
                    text=f"{title}\n\n{summary}",
                )
            )
        return stories


def _entry_date(entry) -> datetime.date | None:
    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            return datetime.date(value.tm_year, value.tm_mon, value.tm_mday)
    return None
