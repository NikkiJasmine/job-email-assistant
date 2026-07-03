import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.story_scout import main
from src.story_scout.models import RawStory


def _fake_config(top_n=5):
    return type(
        "Config",
        (),
        {
            "anthropic_api_key": "key",
            "claude_model": "claude-sonnet-5",
            "notion_token": "token",
            "notion_story_database_id": "db-id",
            "google_client_id": "id",
            "google_client_secret": "secret",
            "google_refresh_token": "refresh",
            "notify_email": "me@example.com",
            "recipient_name": "Nicole",
            "lookback_days": 4,
            "top_n": top_n,
            "reddit_client_id": "",
            "reddit_client_secret": "",
            "youtube_api_key": "",
        },
    )()


def _raw_story(url, fetch_comments=None):
    return RawStory(
        source_name="Adweek",
        platform="RSS",
        title="A story",
        url=url,
        published_at=datetime.date(2026, 7, 1),
        text="A story",
        fetch_comments=fetch_comments,
    )


def _source_with_stories(stories):
    source = MagicMock()
    source.name = "Fake Source"
    source.fetch_recent.return_value = stories
    return source


def _package_mock():
    package = MagicMock()
    package.score = None
    package.score_reason = ""
    return package


@patch("src.story_scout.main.notifier.send_digest_email")
@patch("src.story_scout.main.gmail_client.build_service")
@patch("src.story_scout.main.report.build_report", return_value="a report")
@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_raises_when_every_top_story_fails(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
    mock_build_report,
    mock_build_service,
    mock_send_digest,
):
    mock_load_config.return_value = _fake_config()
    stories = [_raw_story("https://a.com/1"), _raw_story("https://a.com/2")]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = False

    mock_llm = MagicMock()
    mock_llm.score_stories.return_value = [(stories[0], 9, "great"), (stories[1], 8, "good")]
    mock_llm.generate_package.side_effect = Exception("boom")
    mock_llm_cls.return_value = mock_llm

    with pytest.raises(RuntimeError, match="All 2 top-scored stor"):
        main.run()


@patch("src.story_scout.main.notifier.send_digest_email")
@patch("src.story_scout.main.gmail_client.build_service")
@patch("src.story_scout.main.report.build_report", return_value="a report")
@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_does_not_raise_when_only_some_stories_fail(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
    mock_build_report,
    mock_build_service,
    mock_send_digest,
):
    mock_load_config.return_value = _fake_config()
    stories = [_raw_story("https://a.com/1"), _raw_story("https://a.com/2")]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = False

    mock_llm = MagicMock()
    mock_llm.score_stories.return_value = [(stories[0], 9, "great"), (stories[1], 8, "good")]
    mock_llm.generate_package.side_effect = [Exception("boom"), _package_mock()]
    mock_llm_cls.return_value = mock_llm

    main.run()  # should not raise


@patch("src.story_scout.main.notifier.send_digest_email")
@patch("src.story_scout.main.gmail_client.build_service")
@patch("src.story_scout.main.report.build_report", return_value="a report")
@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_does_not_raise_when_no_candidates(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
    mock_build_report,
    mock_build_service,
    mock_send_digest,
):
    mock_load_config.return_value = _fake_config()
    mock_get_sources.return_value = [_source_with_stories([])]
    mock_dedup.return_value = []
    mock_already_logged.return_value = False

    mock_llm = MagicMock()
    mock_llm.score_stories.return_value = []
    mock_llm.synthesize_patterns.return_value = ""
    mock_llm_cls.return_value = mock_llm

    main.run()  # should not raise
    mock_llm.generate_package.assert_not_called()
    mock_send_digest.assert_called_once_with(mock_build_service.return_value, "me@example.com", "a report", [])


@patch("src.story_scout.main.notifier.send_digest_email")
@patch("src.story_scout.main.gmail_client.build_service")
@patch("src.story_scout.main.report.build_report", return_value="a report")
@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_keeps_only_top_n_by_score(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
    mock_build_report,
    mock_build_service,
    mock_send_digest,
):
    mock_load_config.return_value = _fake_config(top_n=1)
    stories = [_raw_story("https://a.com/low"), _raw_story("https://a.com/high")]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = False

    mock_llm = MagicMock()
    mock_llm.score_stories.return_value = [(stories[0], 2, "meh"), (stories[1], 9, "great")]
    mock_llm.generate_package.return_value = _package_mock()
    mock_llm_cls.return_value = mock_llm

    main.run()

    assert mock_llm.generate_package.call_count == 1
    (called_story, _comments), _ = mock_llm.generate_package.call_args
    assert called_story.url == "https://a.com/high"


@patch("src.story_scout.main.notifier.send_digest_email")
@patch("src.story_scout.main.gmail_client.build_service")
@patch("src.story_scout.main.report.build_report", return_value="a report")
@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_fetches_comments_for_top_stories_before_generating(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
    mock_build_report,
    mock_build_service,
    mock_send_digest,
):
    mock_load_config.return_value = _fake_config()
    fetch_comments = MagicMock(return_value="Real comment text")
    stories = [_raw_story("https://a.com/1", fetch_comments=fetch_comments)]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = False

    mock_llm = MagicMock()
    mock_llm.score_stories.return_value = [(stories[0], 9, "great")]
    mock_llm.generate_package.return_value = _package_mock()
    mock_llm_cls.return_value = mock_llm

    main.run()

    fetch_comments.assert_called_once()
    (_story_arg, comments_arg), _ = mock_llm.generate_package.call_args
    assert comments_arg == "Real comment text"


@patch("src.story_scout.main.notifier.send_digest_email")
@patch("src.story_scout.main.gmail_client.build_service")
@patch("src.story_scout.main.report.build_report", return_value="a report")
@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_skips_stories_already_logged_in_notion(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
    mock_build_report,
    mock_build_service,
    mock_send_digest,
):
    mock_load_config.return_value = _fake_config()
    stories = [_raw_story("https://a.com/1")]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = True

    mock_llm = MagicMock()
    mock_llm.score_stories.return_value = []
    mock_llm_cls.return_value = mock_llm

    main.run()

    mock_llm.score_stories.assert_called_once_with([])


@patch("src.story_scout.main.notifier.send_digest_email")
@patch("src.story_scout.main.gmail_client.build_service")
@patch("src.story_scout.main.report.build_report", return_value="a report")
@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_does_not_raise_when_digest_email_fails(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
    mock_build_report,
    mock_build_service,
    mock_send_digest,
):
    mock_load_config.return_value = _fake_config()
    stories = [_raw_story("https://a.com/1")]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = False
    mock_send_digest.side_effect = Exception("smtp down")

    mock_llm = MagicMock()
    mock_llm.score_stories.return_value = [(stories[0], 9, "great")]
    mock_llm.generate_package.return_value = _package_mock()
    mock_llm_cls.return_value = mock_llm

    main.run()  # Notion write succeeded -- a notify failure must not raise
