import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.story_scout import main
from src.story_scout.models import RawStory


def _fake_config():
    return type(
        "Config",
        (),
        {
            "anthropic_api_key": "key",
            "claude_model": "claude-sonnet-5",
            "notion_token": "token",
            "notion_story_database_id": "db-id",
            "lookback_days": 2,
        },
    )()


def _raw_story(url):
    return RawStory(
        source_name="Adweek",
        category="Advertising",
        title="A story",
        url=url,
        published_at=datetime.date(2026, 7, 1),
        text="A story",
    )


def _source_with_stories(stories):
    source = MagicMock()
    source.name = "Fake Source"
    source.fetch_recent.return_value = stories
    return source


@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_raises_when_every_relevant_story_fails(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
):
    mock_load_config.return_value = _fake_config()
    stories = [_raw_story("https://a.com/1"), _raw_story("https://a.com/2")]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = False

    mock_llm = MagicMock()
    mock_llm.filter_relevant.return_value = stories
    mock_llm.generate_package.side_effect = Exception("boom")
    mock_llm_cls.return_value = mock_llm

    with pytest.raises(RuntimeError, match="All 2 relevant stor"):
        main.run()


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
):
    mock_load_config.return_value = _fake_config()
    stories = [_raw_story("https://a.com/1"), _raw_story("https://a.com/2")]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = False

    mock_llm = MagicMock()
    mock_llm.filter_relevant.return_value = stories
    mock_llm.generate_package.side_effect = [Exception("boom"), MagicMock()]
    mock_llm_cls.return_value = mock_llm

    main.run()  # should not raise


@patch("src.story_scout.main.notion_writer.build_properties")
@patch("src.story_scout.main.notion_writer.already_logged")
@patch("src.story_scout.main.dedup.remove_duplicates")
@patch("src.story_scout.main.get_enabled_sources")
@patch("src.story_scout.main.StoryScoutLLM")
@patch("src.story_scout.main.notion_client.NotionClient")
@patch("src.story_scout.main.load_config")
def test_run_does_not_raise_when_no_relevant_stories(
    mock_load_config,
    mock_notion_cls,
    mock_llm_cls,
    mock_get_sources,
    mock_dedup,
    mock_already_logged,
    mock_build_props,
):
    mock_load_config.return_value = _fake_config()
    mock_get_sources.return_value = [_source_with_stories([])]
    mock_dedup.return_value = []
    mock_already_logged.return_value = False

    mock_llm = MagicMock()
    mock_llm.filter_relevant.return_value = []
    mock_llm_cls.return_value = mock_llm

    main.run()  # should not raise
    mock_llm.generate_package.assert_not_called()


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
):
    mock_load_config.return_value = _fake_config()
    stories = [_raw_story("https://a.com/1")]
    mock_get_sources.return_value = [_source_with_stories(stories)]
    mock_dedup.return_value = stories
    mock_already_logged.return_value = True

    mock_llm = MagicMock()
    mock_llm.filter_relevant.return_value = []
    mock_llm_cls.return_value = mock_llm

    main.run()

    mock_llm.filter_relevant.assert_called_once_with([])
