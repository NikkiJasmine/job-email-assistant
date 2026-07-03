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
        platform="Instagram",
        text="Caption text pasted in by hand.",
        comments="",
    )
    defaults.update(overrides)
    argv = [
        "--url",
        defaults["url"],
        "--title",
        defaults["title"],
        "--source",
        defaults["source"],
        "--platform",
        defaults["platform"],
        "--text",
        defaults["text"],
    ]
    if defaults["comments"]:
        argv += ["--comments", defaults["comments"]]
    return _parse_args(argv)


def _package_mock():
    return MagicMock(
        brand="Brand A",
        topic="Social Media Strategy",
        summary="s",
        why_it_matters="w",
        public_reaction="No public comment data was available for this source.",
        marketing_lesson="m",
        linkedin_post_angles=["a", "b", "c"],
        score=None,
        score_reason="",
    )


@patch("src.story_scout.manual_entry.StoryScoutLLM")
@patch("src.story_scout.manual_entry.notion_writer.already_logged")
@patch("src.story_scout.manual_entry.notion_client.NotionClient")
def test_add_story_creates_notion_page(mock_notion_cls, mock_already_logged, mock_llm_cls):
    mock_already_logged.return_value = False
    mock_llm = MagicMock()
    mock_llm.generate_package.return_value = _package_mock()
    mock_llm_cls.return_value = mock_llm
    mock_notion = MagicMock()
    mock_notion_cls.return_value = mock_notion

    add_story(_fake_config(), _args())

    mock_llm.generate_package.assert_called_once()
    mock_notion.create_page.assert_called_once()


@patch("src.story_scout.manual_entry.StoryScoutLLM")
@patch("src.story_scout.manual_entry.notion_writer.already_logged")
@patch("src.story_scout.manual_entry.notion_client.NotionClient")
def test_add_story_passes_pasted_comments_through(mock_notion_cls, mock_already_logged, mock_llm_cls):
    mock_already_logged.return_value = False
    mock_llm = MagicMock()
    mock_llm.generate_package.return_value = _package_mock()
    mock_llm_cls.return_value = mock_llm
    mock_notion_cls.return_value = MagicMock()

    add_story(_fake_config(), _args(comments="Someone said this was tone-deaf."))

    _, kwargs = mock_llm.generate_package.call_args
    assert kwargs["comments_text"] == "Someone said this was tone-deaf."


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
