import datetime
from unittest.mock import patch

from src.story_scout.sources.rss import RSSSource


class _FakeParsedFeed:
    def __init__(self, bozo, entries, bozo_exception=None):
        self.bozo = bozo
        self.entries = entries
        self._bozo_exception = bozo_exception

    def get(self, key, default=None):
        if key == "bozo_exception":
            return self._bozo_exception
        return getattr(self, key, default)


def _entry(title, link, published_parsed=None, summary="a summary"):
    return {"title": title, "link": link, "summary": summary, "published_parsed": published_parsed}


@patch("src.story_scout.sources.rss.feedparser.parse")
def test_fetch_recent_filters_by_published_date(mock_parse):
    old = datetime.date(2020, 1, 1).timetuple()
    recent = datetime.date(2026, 7, 1).timetuple()
    mock_parse.return_value = _FakeParsedFeed(
        bozo=False,
        entries=[
            _entry("Old story", "https://a.com/1", published_parsed=old),
            _entry("Recent story", "https://a.com/2", published_parsed=recent),
        ],
    )

    source = RSSSource("Test Feed", "https://a.com/feed")
    stories = source.fetch_recent(since=datetime.date(2026, 6, 30))

    assert [s.title for s in stories] == ["Recent story"]
    assert stories[0].platform == "RSS"
    assert stories[0].source_name == "Test Feed"


@patch("src.story_scout.sources.rss.feedparser.parse")
def test_fetch_recent_skips_entries_missing_url_or_title(mock_parse):
    mock_parse.return_value = _FakeParsedFeed(
        bozo=False, entries=[{"title": "No link", "summary": "s", "published_parsed": None}]
    )

    source = RSSSource("Test Feed", "https://a.com/feed")
    assert source.fetch_recent(since=datetime.date(2026, 1, 1)) == []


@patch("src.story_scout.sources.rss.feedparser.parse")
def test_fetch_recent_returns_empty_on_parse_failure(mock_parse):
    mock_parse.return_value = _FakeParsedFeed(bozo=True, entries=[], bozo_exception=Exception("bad xml"))

    source = RSSSource("Broken Feed", "https://a.com/feed")
    assert source.fetch_recent(since=datetime.date(2026, 1, 1)) == []
