"""Hourly pipeline: Gmail -> relevance check -> summarize/classify/draft -> Gmail draft + Notion."""

import datetime
import logging

from src.common import gmail_client, notion_client
from src.common.config import load_config
from src.common.llm_client import LLMClient, LLMProviderError
from src.job_assistant.models import (
    CATEGORY,
    DEFAULT_STAGE_FOR_NEW_ROW,
    NEEDS_AI_REVIEW_STATUS,
    STAGE_MAPPING,
    TRACK,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("job_assistant")


def _build_notion_properties(thread, analysis, is_new_row: bool) -> dict:
    today = datetime.date.today().isoformat()
    name = f"{analysis.company or 'Unknown Company'} — {analysis.role or thread.sender_name}"

    properties = {
        "Name": notion_client.title_prop(name),
        "Company": notion_client.text_prop(analysis.company),
        "Role / Job Title": notion_client.text_prop(analysis.role),
        "Recruiter Name": notion_client.text_prop(thread.sender_name),
        "Recruiter Email": notion_client.email_prop(thread.sender_email),
        "Date Received": notion_client.date_prop(today),
        "Status": notion_client.select_prop(analysis.classification),
        "Email Summary": notion_client.text_prop(
            f"{analysis.summary}\n\nWhat they want: {analysis.what_recruiter_wants}"
        ),
        "Suggested Reply": notion_client.text_prop(analysis.suggested_reply),
        "Gmail Thread Link": notion_client.url_prop(gmail_client.thread_link(thread.thread_id)),
        "Gmail Thread ID": notion_client.text_prop(thread.thread_id),
        "Last Processed Message ID": notion_client.text_prop(thread.message_id),
    }

    stage = STAGE_MAPPING.get(analysis.classification)
    if stage:
        properties["Stage"] = notion_client.select_prop(stage)
    elif is_new_row:
        properties["Stage"] = notion_client.select_prop(DEFAULT_STAGE_FOR_NEW_ROW)

    if is_new_row:
        properties["Track"] = notion_client.select_prop(TRACK)
        properties["Category"] = notion_client.select_prop(CATEGORY)

    return properties


def _build_needs_review_notion_properties(thread, is_new_row: bool) -> dict:
    """Fallback properties written when the LLM provider itself failed (outage,
    no credits, invalid key, rate limit, etc) -- no analysis is available, so
    this just logs the email and its raw body for manual triage instead of
    losing the thread entirely.

    Deliberately leaves "Last Processed Message ID" unset: that field is what
    the dedup check in _process_thread compares against, so leaving it empty
    means this thread is retried against the LLM on every subsequent run
    (self-healing once the provider recovers) instead of being silently
    skipped forever.
    """
    name = f"{thread.sender_name} — {thread.subject or 'Needs AI Review'}"

    properties = {
        "Name": notion_client.title_prop(name),
        "Recruiter Name": notion_client.text_prop(thread.sender_name),
        "Recruiter Email": notion_client.email_prop(thread.sender_email),
        "Date Received": notion_client.date_prop(datetime.date.today().isoformat()),
        "Status": notion_client.select_prop(NEEDS_AI_REVIEW_STATUS),
        "Raw Email Body": notion_client.text_prop(thread.body_text),
        "Gmail Thread Link": notion_client.url_prop(gmail_client.thread_link(thread.thread_id)),
        "Gmail Thread ID": notion_client.text_prop(thread.thread_id),
    }

    if is_new_row:
        properties["Track"] = notion_client.select_prop(TRACK)
        properties["Category"] = notion_client.select_prop(CATEGORY)
        properties["Stage"] = notion_client.select_prop(DEFAULT_STAGE_FOR_NEW_ROW)

    return properties


def run() -> None:
    config = load_config()

    gmail = gmail_client.build_service(
        config.google_client_id, config.google_client_secret, config.google_refresh_token
    )
    notion = notion_client.NotionClient(config.notion_token, config.notion_data_source_id)
    llm = LLMClient(config.llm_provider, config.llm_api_key, config.llm_model)

    thread_ids = gmail_client.search_candidate_threads(gmail, config.max_emails_per_run)
    logger.info("Found %d candidate thread(s) to check", len(thread_ids))

    failure_count = 0
    for thread_id in thread_ids:
        try:
            _process_thread(gmail, notion, llm, thread_id)
        except Exception:
            failure_count += 1
            logger.exception("Failed processing thread %s; will retry next run", thread_id)

    if failure_count:
        logger.warning("%d of %d thread(s) failed this run", failure_count, len(thread_ids))
    # If every single candidate failed, this is very unlikely to be a batch
    # of unrelated per-email flukes -- it's much more likely a systemic
    # problem (bad credentials, wrong Notion database id, etc). Fail the run
    # loudly so GitHub Actions reports it as failed and the built-in
    # failure-email notification actually fires, instead of silently
    # reporting success while nothing worked.
    if thread_ids and failure_count == len(thread_ids):
        raise RuntimeError(
            f"All {failure_count} candidate thread(s) failed to process -- "
            "likely a systemic issue (credentials, Notion database id, etc), "
            "not per-email flukes. See exception logs above for the root cause."
        )


def _process_thread(gmail, notion, llm, thread_id: str) -> None:
    thread = gmail_client.get_thread(gmail, thread_id)

    # Dedup: skip entirely (no LLM calls) if we've already processed this
    # thread's current latest message. A new message on a previously-seen
    # thread has a different message_id, so it will NOT be skipped.
    existing_page = notion.find_page_by_thread_id(thread_id)
    if existing_page and existing_page.last_processed_message_id == thread.message_id:
        logger.info("Thread %s already processed, skipping", thread_id)
        return

    try:
        if not llm.is_job_related(thread.body_text):
            logger.info("Thread %s judged not job-related, skipping", thread_id)
            return
        analysis = llm.analyze_email(thread.body_text)
    except LLMProviderError:
        # The LLM provider itself is unavailable (outage, no credits, invalid
        # key, rate limit, etc) -- this is not this email's fault, and it
        # should never fail the whole run. Log the thread to Notion flagged
        # for manual review (with the raw body saved) and move on; the next
        # run will retry it like any other unprocessed thread.
        logger.exception(
            "LLM provider failed for thread %s; flagging for manual review", thread_id
        )
        properties = _build_needs_review_notion_properties(
            thread, is_new_row=existing_page is None
        )
        if existing_page:
            notion.update_page(existing_page.page_id, properties)
        else:
            notion.create_page(properties)
        logger.info("Thread %s logged with status '%s'", thread_id, NEEDS_AI_REVIEW_STATUS)
        return

    logger.info("Thread %s classified as %s", thread_id, analysis.classification)

    # Fallback dedup: a thread-id match means we've already seen *this*
    # Gmail thread, but the same application can resurface on a different
    # thread (e.g. a recruiter starting a fresh subject line instead of
    # replying inline). Before creating a new row, also check for an
    # existing record with the same Company + Role / Job Title and update
    # that instead of creating a duplicate. Skipped when either is blank --
    # matching on an empty Company/Role would merge unrelated applications.
    if existing_page is None and analysis.company and analysis.role:
        existing_page = notion.find_page_by_company_and_role(analysis.company, analysis.role)
        if existing_page:
            logger.info(
                "Thread %s matched existing application for %s / %s by Company + Role",
                thread_id,
                analysis.company,
                analysis.role,
            )

    properties = _build_notion_properties(thread, analysis, is_new_row=existing_page is None)

    if existing_page:
        notion.update_page(existing_page.page_id, properties)
    else:
        notion.create_page(properties)

    gmail_client.create_draft_reply(gmail, thread, analysis.suggested_reply)
    logger.info("Thread %s processed: draft created, Notion updated", thread_id)


if __name__ == "__main__":
    run()
