from unittest.mock import MagicMock, patch

from src.story_scout.manual_entry import _parse_args, add_story


def _fake_config():
    return type(
        "Config",
        (),
        {
            "anthropic_api_key": "key",
            "claude_model": "claude-sonnet-5",
            "notion_token": "token",
            "notion_story_database_id": "db-id",
        },
    )()


def _args(**overrides):
    defaults = dict(
        url="https://www.instagram.com/p/abc123/",
        title="Silence, brand",
        source="Instagram (@girlsinmarketing)",
        category="Social Media",
        text="Caption text pasted in by hand.",
    )
    defaults.update(overrides)
    return _parse_args(
        [
            "--url",
            defaults["url"],
            "--title",
            defaults["title"],
            "--source",
            defaults["source"],
            "--category",
            defaults["category"],
            "--text",
            defaults["text"],
        ]
    )


@patch("src.story_scout.manual_entry.StoryScoutLLM")
@patch("src.story_scout.manual_entry.notion_writer.already_logged")
@patch("src.story_scout.manual_entry.notion_client.NotionClient")
def test_add_story_creates_notion_page(mock_notion_cls, mock_already_logged, mock_llm_cls):
    mock_already_logged.return_value = False
    mock_llm = MagicMock()
    mock_llm.generate_package.return_value = MagicMock(
        summary="s", key_lessons="k", linkedin_post_ideas=["a", "b", "c"]
    )
    mock_llm_cls.return_value = mock_llm
    mock_notion = MagicMock()
    mock_notion_cls.return_value = mock_notion

    add_story(_fake_config(), _args())

    mock_llm.generate_package.assert_called_once()
    mock_notion.create_page.assert_called_once()


@patch("src.story_scout.manual_entry.StoryScoutLLM")
@patch("src.story_scout.manual_entry.notion_writer.already_logged")
@patch("src.story_scout.manual_entry.notion_client.NotionClient")
def test_add_story_skips_when_already_logged(mock_notion_cls, mock_already_logged, mock_llm_cls):
    mock_already_logged.return_value = True
    mock_llm_cls.return_value = MagicMock()
    mock_notion = MagicMock()
    mock_notion_cls.return_value = mock_notion

    add_story(_fake_config(), _args())

    mock_notion.create_page.assert_not_called()
