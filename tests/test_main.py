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
            "llm_provider": "gemini",
            "llm_api_key": "key",
            "llm_model": "gemini-1.5-flash",
            "gemini_api_key": "gemini-key",
            "gemini_model": "gemini-1.5-flash",
            "notion_token": "token",
            "notion_data_source_id": "db-id",
            "notion_morning_brief_database_id": "brief-db-id",
            "google_client_id": "id",
            "google_client_secret": "secret",
            "google_refresh_token": "refresh",
            "max_emails_per_run": 20,
            "openai_fallback_api_key": None,
            "openai_fallback_model": "gpt-4o-mini",
        },
    )()


def _fake_thread(thread_id="t1", message_id="m1", already_replied=False, attachment_names=None):
    return EmailThread(
        thread_id=thread_id,
        message_id=message_id,
        rfc_message_id="<abc@example.com>",
        subject="Interview next steps",
        sender_name="Jane Recruiter",
        sender_email="jane@acme.com",
        body_text="We would like to schedule an interview.",
        already_replied=already_replied,
        attachment_names=attachment_names or [],
    )


def _fake_analysis(**overrides):
    data = {
        "summary": "s",
        "what_recruiter_wants": "w",
        "classification": "Interview invitation",
        "suggested_reply": "Thanks!",
        "company": "Acme",
        "role": "Engineer",
        "contact_name": "Jane Recruiter",
        "priority": "High",
        "legitimacy_confidence": "High confidence genuine",
        "legitimacy_notes": "",
        "next_action": "Book interview",
    }
    data.update(overrides)
    return EmailAnalysis(**data)


def _notion_no_match():
    notion = MagicMock()
    notion.find_page_by_thread_id.return_value = None
    notion.find_page_by_company.return_value = None
    notion.create_page.return_value = "new-page-id"
    return notion


@patch("src.job_assistant.main._process_thread")
@patch("src.job_assistant.main._daily_career_review")
@patch("src.job_assistant.main.LLMClient")
@patch("src.job_assistant.main.notion_client.NotionClient")
@patch("src.job_assistant.main.gmail_client.build_service")
@patch("src.job_assistant.main.gmail_client.get_or_create_label")
@patch("src.job_assistant.main.gmail_client.search_candidate_threads")
@patch("src.job_assistant.main.load_config")
def test_run_raises_when_every_thread_fails(
    mock_load_config,
    mock_search,
    mock_get_label,
    mock_build_service,
    mock_notion_cls,
    mock_llm_cls,
    mock_review,
    mock_process,
):
    mock_load_config.return_value = _fake_config()
    mock_get_label.return_value = "Label_13"
    mock_search.return_value = ["t1", "t2", "t3"]
    mock_process.side_effect = Exception("boom")
    mock_review.return_value = main.CareerReview()
    mock_notion_cls.return_value = MagicMock()

    with pytest.raises(RuntimeError, match="All 3 candidate thread"):
        main.run()


@patch("src.job_assistant.main._process_thread")
@patch("src.job_assistant.main._daily_career_review")
@patch("src.job_assistant.main.LLMClient")
@patch("src.job_assistant.main.notion_client.NotionClient")
@patch("src.job_assistant.main.gmail_client.build_service")
@patch("src.job_assistant.main.gmail_client.get_or_create_label")
@patch("src.job_assistant.main.gmail_client.search_candidate_threads")
@patch("src.job_assistant.main.load_config")
def test_run_does_not_raise_when_only_some_threads_fail(
    mock_load_config,
    mock_search,
    mock_get_label,
    mock_build_service,
    mock_notion_cls,
    mock_llm_cls,
    mock_review,
    mock_process,
):
    mock_load_config.return_value = _fake_config()
    mock_get_label.return_value = "Label_13"
    mock_search.return_value = ["t1", "t2"]
    mock_process.side_effect = [Exception("boom"), None]
    mock_review.return_value = main.CareerReview()
    mock_notion_cls.return_value = MagicMock()

    main.run()  # should not raise


@patch("src.job_assistant.main._process_thread")
@patch("src.job_assistant.main._daily_career_review")
@patch("src.job_assistant.main.LLMClient")
@patch("src.job_assistant.main.notion_client.NotionClient")
@patch("src.job_assistant.main.gmail_client.build_service")
@patch("src.job_assistant.main.gmail_client.get_or_create_label")
@patch("src.job_assistant.main.gmail_client.search_candidate_threads")
@patch("src.job_assistant.main.load_config")
def test_run_does_not_raise_when_no_candidates(
    mock_load_config,
    mock_search,
    mock_get_label,
    mock_build_service,
    mock_notion_cls,
    mock_llm_cls,
    mock_review,
    mock_process,
):
    mock_load_config.return_value = _fake_config()
    mock_get_label.return_value = "Label_13"
    mock_search.return_value = []
    mock_review.return_value = main.CareerReview()
    mock_notion_cls.return_value = MagicMock()

    main.run()  # should not raise
    mock_process.assert_not_called()


@patch("src.job_assistant.main._daily_career_review")
@patch("src.job_assistant.main.LLMClient")
@patch("src.job_assistant.main.notion_client.NotionClient")
@patch("src.job_assistant.main.gmail_client.build_service")
@patch("src.job_assistant.main.gmail_client.apply_label")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
@patch("src.job_assistant.main.gmail_client.get_or_create_label")
@patch("src.job_assistant.main.gmail_client.search_candidate_threads")
@patch("src.job_assistant.main.load_config")
def test_run_does_not_raise_when_llm_provider_fails_for_every_thread(
    mock_load_config,
    mock_search,
    mock_get_label,
    mock_get_thread,
    mock_create_draft,
    mock_apply_label,
    mock_build_service,
    mock_notion_cls,
    mock_llm_cls,
    mock_review,
):
    """The workflow must never fail just because the AI provider is down --
    even if every single candidate thread hits a provider error, run() should
    complete without raising (each is instead flagged Needs AI Review).
    """
    mock_load_config.return_value = _fake_config()
    mock_get_label.return_value = "Label_13"
    mock_search.return_value = ["t1", "t2"]
    mock_get_thread.side_effect = lambda gmail, thread_id: _fake_thread(thread_id, "m-" + thread_id)
    mock_review.return_value = main.CareerReview()

    mock_notion = _notion_no_match()
    mock_notion_cls.return_value = mock_notion

    mock_llm = MagicMock()
    mock_llm.is_job_related.side_effect = LLMProviderError("provider outage")
    mock_llm_cls.return_value = mock_llm

    main.run()  # should not raise

    assert mock_notion.create_page.call_count == 2
    mock_create_draft.assert_not_called()


# --- _process_thread: LLM provider failure fallback -------------------------


@patch("src.job_assistant.main.gmail_client.apply_label")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_flags_needs_ai_review_on_new_row(mock_get_thread, mock_create_draft, mock_apply_label):
    mock_get_thread.return_value = _fake_thread()
    notion = _notion_no_match()
    llm = MagicMock()
    llm.is_job_related.side_effect = LLMProviderError("no credits")

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1", label_id="Label_13")

    notion.create_page.assert_called_once()
    (properties,) = notion.create_page.call_args[0]
    assert properties["Status"] == {"select": {"name": "Needs AI Review"}}
    assert properties["Raw Email Body"]["rich_text"][0]["text"]["content"] == (
        "We would like to schedule an interview."
    )
    # Deliberately no Last Processed Message ID -- see main._build_needs_review_notion_properties.
    assert "Last Processed Message ID" not in properties
    notion.update_page.assert_not_called()
    notion.append_note.assert_called_once()
    mock_create_draft.assert_not_called()
    # Not labeled either -- must retry against the LLM next run.
    mock_apply_label.assert_not_called()


@patch("src.job_assistant.main.gmail_client.apply_label")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_flags_needs_ai_review_updates_existing_row(
    mock_get_thread, mock_create_draft, mock_apply_label
):
    mock_get_thread.return_value = _fake_thread()
    notion = MagicMock()
    existing_page = type(
        "ExistingPage", (), {"page_id": "page-123", "last_processed_message_id": "old-msg"}
    )()
    notion.find_page_by_thread_id.return_value = existing_page
    llm = MagicMock()
    llm.analyze_email.side_effect = LLMProviderError("rate limited")

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1", label_id="Label_13")

    notion.update_page.assert_called_once()
    page_id, properties = notion.update_page.call_args[0]
    assert page_id == "page-123"
    assert properties["Status"] == {"select": {"name": "Needs AI Review"}}
    notion.create_page.assert_not_called()
    mock_create_draft.assert_not_called()
    mock_apply_label.assert_not_called()


@patch("src.job_assistant.main.gmail_client.apply_label")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_succeeds_normally_when_llm_works(mock_get_thread, mock_create_draft, mock_apply_label):
    mock_get_thread.return_value = _fake_thread()
    notion = _notion_no_match()
    llm = MagicMock()
    llm.is_job_related.return_value = True
    llm.analyze_email.return_value = _fake_analysis()

    gmail = MagicMock()
    outcome = main._process_thread(gmail=gmail, notion=notion, llm=llm, thread_id="t1", label_id="Label_13")

    notion.find_page_by_company.assert_called_once_with("Acme")
    notion.create_page.assert_called_once()
    (properties,) = notion.create_page.call_args[0]
    # Status is one of the constrained conversation-state values, not the
    # classification itself.
    assert properties["Status"]["select"]["name"] in (
        "Active",
        "Messaged",
        "Call Scheduled",
        "Closed",
        "Followed Up",
    )
    assert properties["Priority"] == {"select": {"name": "High"}}
    notion.append_note.assert_called_once()
    mock_create_draft.assert_called_once()
    mock_apply_label.assert_called_once_with(gmail, "t1", "Label_13")
    assert outcome.company == "Acme"
    assert outcome.classification == "Interview invitation"


@patch("src.job_assistant.main.gmail_client.apply_label")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_skips_draft_when_already_replied(mock_get_thread, mock_create_draft, mock_apply_label):
    mock_get_thread.return_value = _fake_thread(already_replied=True)
    notion = _notion_no_match()
    llm = MagicMock()
    llm.is_job_related.return_value = True
    llm.analyze_email.return_value = _fake_analysis()

    outcome = main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1", label_id="Label_13")

    mock_create_draft.assert_not_called()
    (properties,) = notion.create_page.call_args[0]
    assert properties["Status"]["select"]["name"] == "Call Scheduled"  # Interview invitation + already replied
    assert outcome is not None


@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_label_failure_does_not_block_notion_update(mock_get_thread, mock_create_draft):
    """Per the required flow: label attempt -> failure -> log warning ->
    continue -> Notion update always happens regardless."""
    mock_get_thread.return_value = _fake_thread()
    notion = _notion_no_match()
    llm = MagicMock()
    llm.is_job_related.return_value = True
    llm.analyze_email.return_value = _fake_analysis()

    with patch(
        "src.job_assistant.main.gmail_client.apply_label", side_effect=Exception("gmail api error")
    ):
        outcome = main._process_thread(
            gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1", label_id="Label_13"
        )

    notion.create_page.assert_called_once()
    notion.append_note.assert_called_once()
    assert outcome is not None


@patch("src.job_assistant.main.gmail_client.apply_label")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_not_job_related_is_labeled_and_skipped(mock_get_thread, mock_create_draft, mock_apply_label):
    mock_get_thread.return_value = _fake_thread()
    notion = _notion_no_match()
    llm = MagicMock()
    llm.is_job_related.return_value = False

    outcome = main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1", label_id="Label_13")

    assert outcome is None
    notion.create_page.assert_not_called()
    mock_apply_label.assert_called_once()
    llm.analyze_email.assert_not_called()


# --- _process_thread: fallback dedup by Company ------------------------------


@patch("src.job_assistant.main.gmail_client.apply_label")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_updates_existing_application_matched_by_company(
    mock_get_thread, mock_create_draft, mock_apply_label
):
    """A new Gmail thread for an application already tracked under a different
    thread (e.g. a recruiter starting a fresh subject line) should update the
    existing Notion row instead of creating a duplicate.
    """
    mock_get_thread.return_value = _fake_thread(thread_id="t2", message_id="m2")
    notion = MagicMock()
    notion.find_page_by_thread_id.return_value = None  # no match on this thread id
    company_match = type("ExistingPage", (), {"page_id": "page-789", "last_processed_message_id": "old-msg"})()
    notion.find_page_by_company.return_value = company_match
    llm = MagicMock()
    llm.is_job_related.return_value = True
    llm.analyze_email.return_value = _fake_analysis()

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t2", label_id="Label_13")

    notion.find_page_by_company.assert_called_once_with("Acme")
    notion.update_page.assert_called_once()
    page_id, properties = notion.update_page.call_args[0]
    assert page_id == "page-789"
    # Updated, not a new application -- Track/Category shouldn't be (re)stamped.
    assert "Track" not in properties
    assert "Category" not in properties
    notion.create_page.assert_not_called()
    mock_create_draft.assert_called_once()


@patch("src.job_assistant.main.gmail_client.apply_label")
@patch("src.job_assistant.main.gmail_client.create_draft_reply")
@patch("src.job_assistant.main.gmail_client.get_thread")
def test_process_thread_skips_company_lookup_when_company_missing(
    mock_get_thread, mock_create_draft, mock_apply_label
):
    """Matching on an empty Company would silently merge unrelated
    applications, so the fallback lookup must not run when it's blank."""
    mock_get_thread.return_value = _fake_thread()
    notion = MagicMock()
    notion.find_page_by_thread_id.return_value = None
    llm = MagicMock()
    llm.is_job_related.return_value = True
    llm.analyze_email.return_value = _fake_analysis(company="")

    main._process_thread(gmail=MagicMock(), notion=notion, llm=llm, thread_id="t1", label_id="Label_13")

    notion.find_page_by_company.assert_not_called()
    notion.create_page.assert_called_once()


# --- Daily Career Review ------------------------------------------------------


def _review_page(**overrides):
    props = {
        "Name": {"title": [{"plain_text": "Some Row"}]},
        "Company": {"rich_text": [{"plain_text": "Acme"}]},
        "Stage": {"select": {"name": "Applied"}},
        "Status": {"select": {"name": "Active"}},
        "Priority": {"select": {"name": "High"}},
        "Follow-up Date": {"date": None},
        "Date Received": {"date": None},
        "Interview Date": {"date": None},
        "Next Step": {"rich_text": [{"plain_text": "Follow up"}]},
    }
    props.update(overrides)
    return {"properties": props}


def test_daily_career_review_finds_overdue_followup():
    notion = MagicMock()
    notion.query_pages.return_value = [
        _review_page(**{"Follow-up Date": {"date": {"start": "2020-01-01"}}})
    ]

    review = main._daily_career_review(notion)

    assert len(review.overdue_followups) == 1
    assert review.overdue_followups[0].days_overdue > 0


def test_daily_career_review_excludes_closed_stage():
    notion = MagicMock()
    notion.query_pages.return_value = [
        _review_page(
            **{
                "Stage": {"select": {"name": "Rejected"}},
                "Follow-up Date": {"date": {"start": "2020-01-01"}},
            }
        )
    ]

    review = main._daily_career_review(notion)

    assert review.overdue_followups == []


def test_daily_career_review_flags_waiting_too_long():
    notion = MagicMock()
    notion.query_pages.return_value = [
        _review_page(**{"Date Received": {"date": {"start": "2020-01-01"}}})
    ]

    review = main._daily_career_review(notion)

    assert len(review.waiting_too_long) == 1


# --- Morning Brief composition ------------------------------------------------


def test_compose_morning_brief_says_no_new_emails_when_none_found():
    brief = main._compose_morning_brief([], main.CareerReview(), had_candidates=False)
    assert "No new job emails." in brief


def test_compose_morning_brief_includes_priority_actions():
    outcome = main.ThreadOutcome(
        company="Acme",
        role="Engineer",
        contact="Jane",
        classification="Interview invitation",
        priority="Urgent",
        next_action="Reply today",
        legitimacy_confidence="High confidence genuine",
        legitimacy_notes="",
        thread_link="https://mail.google.com/mail/u/0/#all/t1",
    )
    brief = main._compose_morning_brief([outcome], main.CareerReview(), had_candidates=True)
    assert "Reply today (Acme)" in brief
