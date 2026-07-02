import datetime

from src.story_scout.dedup import remove_duplicates
from src.story_scout.models import RawStory


def _story(title, url, source="Source A", category="Marketing"):
    return RawStory(
        source_name=source,
        category=category,
        title=title,
        url=url,
        published_at=datetime.date(2026, 7, 1),
        text=title,
    )


def test_removes_exact_url_duplicates_ignoring_query_and_trailing_slash():
    stories = [
        _story("Brand launches new campaign", "https://example.com/story-1"),
        _story("Brand launches new campaign", "https://example.com/story-1/?utm_source=twitter"),
    ]
    assert len(remove_duplicates(stories)) == 1


def test_removes_near_duplicate_titles_across_sources():
    stories = [
        _story("Nike drops bold new campaign for Gen Z", "https://a.com/1", source="Adweek"),
        _story("Nike drops a bold new campaign for Gen Z", "https://b.com/2", source="Marketing Dive"),
    ]
    assert len(remove_duplicates(stories)) == 1


def test_keeps_distinct_stories():
    stories = [
        _story("Nike drops bold new campaign", "https://a.com/1"),
        _story("Google announces new AI ad tools", "https://b.com/2"),
    ]
    assert len(remove_duplicates(stories)) == 2
