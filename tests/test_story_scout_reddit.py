import datetime
from unittest.mock import MagicMock, patch

from src.story_scout.sources.reddit import RedditSource


def _token_response():
    response = MagicMock()
    response.json.return_value = {"access_token": "tok-123"}
    return response


def _listing_response(posts):
    response = MagicMock()
    response.json.return_value = {"data": {"children": [{"data": post} for post in posts]}}
    return response


@patch("src.story_scout.sources.reddit.httpx.get")
@patch("src.story_scout.sources.reddit.httpx.post")
def test_fetch_recent_builds_raw_stories_with_engagement_note(mock_post, mock_get):
    mock_post.return_value = _token_response()
    mock_get.return_value = _listing_response(
        [
            {
                "title": "Nike's new campaign sparks debate",
                "permalink": "/r/marketing/comments/abc123/nikes_new_campaign/",
                "id": "abc123",
                "selftext": "Some post body",
                "score": 1200,
                "num_comments": 340,
                "created_utc": datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc).timestamp(),
            }
        ]
    )

    source = RedditSource(client_id="id", client_secret="secret", subreddits=["marketing"])
    stories = source.fetch_recent(since=datetime.date(2026, 6, 1))

    assert len(stories) == 1
    story = stories[0]
    assert story.source_name == "r/marketing"
    assert story.platform == "Reddit"
    assert story.url == "https://www.reddit.com/r/marketing/comments/abc123/nikes_new_campaign/"
    assert "1200 upvotes" in story.engagement_note
    assert "340 comments" in story.engagement_note
    assert story.fetch_comments is not None


@patch("src.story_scout.sources.reddit.httpx.get")
@patch("src.story_scout.sources.reddit.httpx.post")
def test_fetch_recent_skips_old_posts(mock_post, mock_get):
    mock_post.return_value = _token_response()
    mock_get.return_value = _listing_response(
        [
            {
                "title": "Old post",
                "permalink": "/r/marketing/comments/old1/old_post/",
                "id": "old1",
                "selftext": "",
                "score": 5,
                "num_comments": 1,
                "created_utc": datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc).timestamp(),
            }
        ]
    )

    source = RedditSource(client_id="id", client_secret="secret", subreddits=["marketing"])
    stories = source.fetch_recent(since=datetime.date(2026, 6, 1))

    assert stories == []


@patch("src.story_scout.sources.reddit.httpx.get")
@patch("src.story_scout.sources.reddit.httpx.post")
def test_fetch_comments_returns_top_comment_bodies(mock_post, mock_get):
    mock_post.return_value = _token_response()
    comments_response = MagicMock()
    comments_response.json.return_value = [
        {},
        {"data": {"children": [{"data": {"body": "Love this campaign"}}, {"data": {"body": "Feels tone-deaf"}}]}},
    ]
    mock_get.return_value = comments_response

    source = RedditSource(client_id="id", client_secret="secret")
    comments = source._fetch_comments("marketing", "abc123")

    assert "Love this campaign" in comments
    assert "Feels tone-deaf" in comments


@patch("src.story_scout.sources.reddit.httpx.get")
@patch("src.story_scout.sources.reddit.httpx.post")
def test_fetch_recent_continues_after_one_subreddit_fails(mock_post, mock_get):
    mock_post.return_value = _token_response()
    mock_get.side_effect = [Exception("boom"), _listing_response([])]

    source = RedditSource(client_id="id", client_secret="secret", subreddits=["broken", "marketing"])
    stories = source.fetch_recent(since=datetime.date(2026, 6, 1))

    assert stories == []
