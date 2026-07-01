from unittest.mock import patch

import pytest

from src.job_assistant import main


def _fake_config():
    return type(
        "Config",
        (),
        {
            "anthropic_api_key": "key",
            "claude_model": "claude-sonnet-5",
            "notion_token": "token",
            "notion_data_source_id": "db-id",
            "google_client_id": "id",
            "google_client_secret": "secret",
            "google_refresh_token": "refresh",
            "max_emails_per_run": 20,
        },
    )()


@patch("src.job_assistant.main._process_thread")
@patch("src.job_assistant.main.LLMClient")
@patch("src.job_assistant.main.notion_client.NotionClient")
@patch("src.job_assistant.main.gmail_client.build_service")
@patch("src.job_assistant.main.gmail_client.search_candidate_threads")
@patch("src.job_assistant.main.load_config")
def test_run_raises_when_every_thread_fails(
    mock_load_config, mock_search, mock_build_service, mock_notion_cls, mock_llm_cls, mock_process
):
    mock_load_config.return_value = _fake_config()
    mock_search.return_value = ["t1", "t2", "t3"]
    mock_process.side_effect = Exception("boom")

    with pytest.raises(RuntimeError, match="All 3 candidate thread"):
        main.run()


@patch("src.job_assistant.main._process_thread")
@patch("src.job_assistant.main.LLMClient")
@patch("src.job_assistant.main.notion_client.NotionClient")
@patch("src.job_assistant.main.gmail_client.build_service")
@patch("src.job_assistant.main.gmail_client.search_candidate_threads")
@patch("src.job_assistant.main.load_config")
def test_run_does_not_raise_when_only_some_threads_fail(
    mock_load_config, mock_search, mock_build_service, mock_notion_cls, mock_llm_cls, mock_process
):
    mock_load_config.return_value = _fake_config()
    mock_search.return_value = ["t1", "t2"]
    mock_process.side_effect = [Exception("boom"), None]

    main.run()  # should not raise


@patch("src.job_assistant.main._process_thread")
@patch("src.job_assistant.main.LLMClient")
@patch("src.job_assistant.main.notion_client.NotionClient")
@patch("src.job_assistant.main.gmail_client.build_service")
@patch("src.job_assistant.main.gmail_client.search_candidate_threads")
@patch("src.job_assistant.main.load_config")
def test_run_does_not_raise_when_no_candidates(
    mock_load_config, mock_search, mock_build_service, mock_notion_cls, mock_llm_cls, mock_process
):
    mock_load_config.return_value = _fake_config()
    mock_search.return_value = []

    main.run()  # should not raise
    mock_process.assert_not_called()
