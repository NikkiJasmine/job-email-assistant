from unittest.mock import MagicMock, patch

import pytest

from src.common.gmail_client import EmailThread
from src.common.llm_client import EmailAnalysis, LLMProviderError
from src.job_assistant import main


def _fake_config():
    return type(
        "Config",
        (),
        {
            "llm_provider": "anthropic",
            "llm_api_key": "key",
            "llm_model": "claude-sonnet-5",
            "notion_token": "token",
            "notion_data_source_id": "db-id",
            "google_client_id": "id",
            "google_client_secret": "secret",
            "google_refresh_token": "refresh",
            "max_emails_per_run": 20,
        },
    )()


def _fake_thread(thread_id="t1", message_id="m1"):
    return EmailThread(
        thread_id=thread_id,
        message_id=message_id,
        rfc_message_id="<abc@example.com>",
        subject="Interview next steps",
        sender_name="Jane Recruiter",
        sender_email="jane@acme.com",
        body_text="We would like to schedule an interview.",
    )


def _fake_analysis():
    return EmailAnalysis(
        summary="s",
        what_recruiter_wants="w",
        classification="Next Step",
        suggested_reply="Thanks!",
        company="Acme",
        role="Engineer",
    )


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


@patch("src.job_assistant.main.LLMClient")
@patch("src.job_assistant.main.notion_client.NotionClient")
@patch("src.job_assistant.main.gmail_client.build_service")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
@patch("src.job_assistant.main.gmail_client.search_candidate_threads")
@patch("src.job_assistant.main.load_config")
def test_run_does_not_raise_when_llm_provider_fails_for_every_thread(
    mock_load_config,
    mock_search,
    mock_get_thread,
    mock_create_draft,
    mock_build_service,
    mock_notion_cls,
    mock_llm_cls,
):
    """The workflow must never fail just because the AI provider is down --
    even if every single candidate thread hits a provider error, run() should
    complete without raising (each is instead flagged Needs AI Review).
    """
    mock_load_config.return_value = _fake_config()
    mock_search.return_value = ["t1", "t2"]
    mock_get_thread.side_effect = lambda gmail, thread_id: _fake_thread(thread_id, "m-" + thread_id)

    mock_notion = MagicMock()
    mock_notion.find_page_by_thread_id.return_value = None
    mock_notion_cls.return_value = mock_notion

    mock_llm = MagicMock()
    mock_llm.is_job_related.side_effect = LLMProviderError("provider outage")
    mock_llm_cls.return_value = mock_llm

    main.run()  # should not raise

    assert mock_notion.create_page.call_count == 2
    mock_create_draft.assert_not_called()


# --- _process_thread: LLM provider failure fallback -------------------------


@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_flags_needs_ai_review_on_new_row(mock_get_thread, mock_create_draft):
    mock_get_thread.return_value = _fake_thread()
    notion = MagicMock()
    notion.find_page_by_thread_id.return_value = None
    llm = MagicMock()
    llm.is_job_related.side_effect = LLMProviderError("no credits")

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1")

    notion.create_page.assert_called_once()
    (properties,) = notion.create_page.call_args[0]
    assert properties["Status"] == {"select": {"name": "Needs AI Review"}}
    assert properties["Raw Email Body"]["rich_text"][0]["text"]["content"] == (
        "We would like to schedule an interview."
    )
    # Deliberately no Last Processed Message ID -- see main._build_needs_review_notion_properties.
    assert "Last Processed Message ID" not in properties
    notion.update_page.assert_not_called()
    mock_create_draft.assert_not_called()


@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_flags_needs_ai_review_updates_existing_row(
    mock_get_thread, mock_create_draft
):
    mock_get_thread.return_value = _fake_thread()
    notion = MagicMock()
    existing_page = type(
        "ExistingPage", (), {"page_id": "page-123", "last_processed_message_id": "old-msg"}
    )()
    notion.find_page_by_thread_id.return_value = existing_page
    llm = MagicMock()
    llm.analyze_email.side_effect = LLMProviderError("rate limited")

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1")

    notion.update_page.assert_called_once()
    page_id, properties = notion.update_page.call_args[0]
    assert page_id == "page-123"
    assert properties["Status"] == {"select": {"name": "Needs AI Review"}}
    notion.create_page.assert_not_called()
    mock_create_draft.assert_not_called()


@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_succeeds_normally_when_llm_works(mock_get_thread, mock_create_draft):
    mock_get_thread.return_value = _fake_thread()
    notion = MagicMock()
    notion.find_page_by_thread_id.return_value = None
    notion.find_page_by_company_and_role.return_value = None
    llm = MagicMock()
    llm.is_job_related.return_value = True
    llm.analyze_email.return_value = _fake_analysis()

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1")

    notion.find_page_by_company_and_role.assert_called_once_with("Acme", "Engineer")
    notion.create_page.assert_called_once()
    (properties,) = notion.create_page.call_args[0]
    assert properties["Status"] == {"select": {"name": "Next Step"}}
    mock_create_draft.assert_called_once()


# --- _process_thread: fallback dedup by Company + Role / Job Title ----------


@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_updates_existing_application_matched_by_company_and_role(
    mock_get_thread, mock_create_draft
):
    """A new Gmail thread for an application already tracked under a different
    thread (e.g. a recruiter starting a fresh subject line) should update the
    existing Notion row instead of creating a duplicate.
    """
    mock_get_thread.return_value = _fake_thread(thread_id="t2", message_id="m2")
    notion = MagicMock()
    notion.find_page_by_thread_id.return_value = None  # no match on this thread id
    company_role_match = type(
        "ExistingPage", (), {"page_id": "page-789", "last_processed_message_id": "old-msg"}
    )()
    notion.find_page_by_company_and_role.return_value = company_role_match
    llm = MagicMock()
    llm.is_job_related.return_value = True
    llm.analyze_email.return_value = _fake_analysis()

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t2")

    notion.find_page_by_company_and_role.assert_called_once_with("Acme", "Engineer")
    notion.update_page.assert_called_once()
    page_id, properties = notion.update_page.call_args[0]
    assert page_id == "page-789"
    # Updated, not a new application -- Track/Category shouldn't be (re)stamped.
    assert "Track" not in properties
    assert "Category" not in properties
    notion.create_page.assert_not_called()
    mock_create_draft.assert_called_once()


@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_skips_company_role_lookup_when_company_missing(
    mock_get_thread, mock_create_draft
):
    """Matching on an empty Company/Role would silently merge unrelated
    applications, so the fallback lookup must not run when either is blank.
    """
    mock_get_thread.return_value = _fake_thread()
    notion = MagicMock()
    notion.find_page_by_thread_id.return_value = None
    llm = MagicMock()
    llm.is_job_related.return_value = True
    analysis = _fake_analysis()
    analysis.company = ""
    llm.analyze_email.return_value = analysis

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1")

    notion.find_page_by_company_and_role.assert_not_called()
    notion.create_page.assert_called_once()
