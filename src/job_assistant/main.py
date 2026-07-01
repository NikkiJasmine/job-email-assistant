"""Hourly pipeline: Gmail -> relevance check -> summarize/classify/draft -> Gmail draft + Notion."""

import datetime
import logging

from src.common import gmail_client, notion_client
from src.common.config import load_config
from src.common.llm_client import LLMClient
from src.job_assistant.models import (
    CATEGORY,
    DEFAULT_STAGE_FOR_NEW_ROW,
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


def run() -> None:
    config = load_config()

    gmail = gmail_client.build_service(
        config.google_client_id, config.google_client_secret, config.google_refresh_token
    )
    notion = notion_client.NotionClient(config.notion_token, config.notion_data_source_id)
    llm = LLMClient(config.anthropic_api_key, config.claude_model)

    thread_ids = gmail_client.search_candidate_threads(gmail, config.max_emails_per_run)
    logger.info("Found %d candidate thread(s) to check", len(thread_ids))

    for thread_id in thread_ids:
        try:
            _process_thread(gmail, notion, llm, thread_id)
        except Exception:
            logger.exception("Failed processing thread %s; will retry next run", thread_id)


def _process_thread(gmail, notion, llm, thread_id: str) -> None:
    thread = gmail_client.get_thread(gmail, thread_id)

    # Dedup: skip entirely (no LLM calls) if we've already processed this
    # thread's current latest message. A new message on a previously-seen
    # thread has a different message_id, so it will NOT be skipped.
    existing_page = notion.find_page_by_thread_id(thread_id)
    if existing_page and existing_page.last_processed_message_id == thread.message_id:
        logger.info("Thread %s already processed, skipping", thread_id)
        return

    if not llm.is_job_related(thread.body_text):
        logger.info("Thread %s judged not job-related, skipping", thread_id)
        return

    analysis = llm.analyze_email(thread.body_text)
    logger.info("Thread %s classified as %s", thread_id, analysis.classification)

    properties = _build_notion_properties(thread, analysis, is_new_row=existing_page is None)

    if existing_page:
        notion.update_page(existing_page.page_id, properties)
    else:
        notion.create_page(properties)

    gmail_client.create_draft_reply(gmail, thread, analysis.suggested_reply)
    logger.info("Thread %s processed: draft created, Notion updated", thread_id)


if __name__ == "__main__":
    run()
