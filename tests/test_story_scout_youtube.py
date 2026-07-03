import datetime
from unittest.mock import MagicMock, patch

from src.story_scout.sources.youtube import YouTubeSource


def _search_response(video_ids):
    response = MagicMock()
    response.json.return_value = {"items": [{"id": {"videoId": vid}} for vid in video_ids]}
    return response


def _videos_response(items):
    response = MagicMock()
    response.json.return_value = {"items": items}
    return response


@patch("src.story_scout.sources.youtube.httpx.get")
def test_fetch_recent_builds_raw_stories_with_engagement_note(mock_get):
    mock_get.side_effect = [
        _search_response(["vid1"]),
        _videos_response(
            [
                {
                    "id": "vid1",
                    "snippet": {
                        "title": "Brand X launches AI ad campaign",
                        "description": "A description",
                        "channelTitle": "Marketing Channel",
                        "publishedAt": "2026-07-01T00:00:00Z",
                    },
                    "statistics": {"viewCount": "50000", "commentCount": "800"},
                }
            ]
        ),
    ]

    source = YouTubeSource(api_key="key", queries=["marketing campaign"])
    stories = source.fetch_recent(since=datetime.date(2026, 6, 1))

    assert len(stories) == 1
    story = stories[0]
    assert story.platform == "YouTube"
    assert story.source_name == "Marketing Channel"
    assert story.url == "https://www.youtube.com/watch?v=vid1"
    assert "50000 views" in story.engagement_note
    assert "800 comments" in story.engagement_note
    assert story.fetch_comments is not None


@patch("src.story_scout.sources.youtube.httpx.get")
def test_fetch_recent_returns_empty_when_no_search_results(mock_get):
    mock_get.return_value = _search_response([])

    source = YouTubeSource(api_key="key", queries=["marketing campaign"])
    stories = source.fetch_recent(since=datetime.date(2026, 6, 1))

    assert stories == []


@patch("src.story_scout.sources.youtube.httpx.get")
def test_fetch_recent_continues_after_one_query_fails(mock_get):
    mock_get.side_effect = [Exception("boom"), _search_response([])]

    source = YouTubeSource(api_key="key", queries=["broken query", "marketing campaign"])
    stories = source.fetch_recent(since=datetime.date(2026, 6, 1))

    assert stories == []


@patch("src.story_scout.sources.youtube.httpx.get")
def test_fetch_comments_returns_empty_when_comments_disabled(mock_get):
    import httpx

    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError("403", request=MagicMock(), response=MagicMock())
    mock_get.return_value = response

    source = YouTubeSource(api_key="key")
    assert source._fetch_comments("vid1") == ""


@patch("src.story_scout.sources.youtube.httpx.get")
def test_fetch_comments_returns_top_level_comment_text(mock_get):
    response = MagicMock()
    response.json.return_value = {
        "items": [
            {"snippet": {"topLevelComment": {"snippet": {"textDisplay": "Love this!"}}}},
            {"snippet": {"topLevelComment": {"snippet": {"textDisplay": "Not a fan"}}}},
        ]
    }
    mock_get.return_value = response

    source = YouTubeSource(api_key="key")
    comments = source._fetch_comments("vid1")

    assert "Love this!" in comments
    assert "Not a fan" in comments
