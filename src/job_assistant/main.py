"""Morning Job Brief pipeline.

Gmail (label-deduped) -> relevance + legitimacy analysis (Gemini, hardcoded --
see CLAUDE.md for why this pipeline doesn't use LLM_PROVIDER) -> Notion CRM
update -> Gmail draft + best-effort label -> Daily Career Review -> Morning
Brief delivered to Notion.

Runs once daily via GitHub Actions (.github/workflows/morning-job-brief.yml).
"""

import datetime
import logging
from dataclasses import dataclass, field

from src.common import gmail_client, notion_client
from src.common.config import load_config
from src.common.llm_client import EmailAnalysis, LLMClient, LLMProviderError
from src.job_assistant.models import (
    CATEGORY,
    DEFAULT_STAGE_FOR_NEW_ROW,
    JOB_BOT_LABEL_NAME,
    NEEDS_AI_REVIEW_STATUS,
    STAGE_MAPPING,
    TRACK,
    determine_status,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("job_assistant")

# "Waiting longer than 7 days without a response" per the Daily Career Review spec.
_WAITING_TOO_LONG_DAYS = 7
_MAX_PRIORITY_ACTIONS = 5
_CLOSED_STAGES = {"Rejected", "Closed"}
_CLOSED_STATUSES = {"Closed"}


@dataclass
class ThreadOutcome:
    """What happened for one processed thread -- feeds the Morning Brief."""

    company: str
    role: str
    contact: str
    classification: str
    priority: str
    next_action: str
    legitimacy_confidence: str
    legitimacy_notes: str
    thread_link: str


def _contact_name(analysis_contact_name: str, company: str, sender_name: str) -> str:
    if analysis_contact_name:
        return analysis_contact_name
    if company:
        return f"{company} Recruiting"
    return sender_name or "Recruiting"


def _email_context(thread: gmail_client.EmailThread) -> str:
    """Includes sender/subject alongside the body so the LLM's legitimacy
    check has the sender domain to compare against the claimed company."""
    return (
        f"From: {thread.sender_name} <{thread.sender_email}>\n"
        f"Subject: {thread.subject}\n\n"
        f"{thread.body_text}"
    )


def _build_notion_properties(
    thread: gmail_client.EmailThread, analysis: EmailAnalysis, contact: str, is_new_row: bool
) -> dict:
    today = datetime.date.today().isoformat()
    name = f"{analysis.company or 'Unknown Company'} — {analysis.role or contact}"
    status = determine_status(analysis.classification, thread.already_replied, analysis.next_action)

    properties = {
        "Name": notion_client.title_prop(name),
        "Company": notion_client.text_prop(analysis.company),
        "Role / Job Title": notion_client.text_prop(analysis.role),
        "Recruiter Name": notion_client.text_prop(contact),
        "Recruiter Email": notion_client.email_prop(thread.sender_email),
        "Date Received": notion_client.date_prop(today),
        "Last Contact": notion_client.date_prop(today),
        "Status": notion_client.select_prop(status),
        "Priority": notion_client.select_prop(analysis.priority),
        "Email Summary": notion_client.text_prop(
            f"[{analysis.classification}] {analysis.summary}\n\n"
            f"What they want: {analysis.what_recruiter_wants}"
        ),
        "Suggested Reply": notion_client.text_prop(analysis.suggested_reply),
        "Next Step": notion_client.text_prop(analysis.next_action),
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


def _build_needs_review_notion_properties(thread: gmail_client.EmailThread, is_new_row: bool) -> dict:
    """Fallback properties written when the LLM provider itself failed (outage,
    no credits, invalid key, rate limit, etc) -- no analysis is available, so
    this just logs the email and its raw body for manual triage instead of
    losing the thread entirely.

    Deliberately leaves "Last Processed Message ID" unset: that field is what
    the dedup check compares against, so leaving it empty means this thread
    is retried against the LLM on every subsequent run (self-healing once the
    provider recovers) instead of being silently skipped forever. The Gmail
    label is NOT applied for these either, for the same reason.
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


def _apply_label_best_effort(gmail, thread_id: str, label_id: str) -> None:
    """Attempt -> success: labeled. Failure: log a warning and continue --
    the Notion update always happens regardless of whether this succeeds.
    Labeling is a convenience for next run's dedup, not a gate on recording
    the outcome."""
    try:
        gmail_client.apply_label(gmail, thread_id, label_id)
    except Exception:
        logger.warning("Failed to apply %s label to thread %s; continuing", JOB_BOT_LABEL_NAME, thread_id, exc_info=True)


def run() -> None:
    config = load_config()

    gmail = gmail_client.build_service(
        config.google_client_id, config.google_client_secret, config.google_refresh_token
    )
    notion = notion_client.NotionClient(config.notion_token, config.notion_data_source_id)
    # Hardcoded to Gemini -- this pipeline deliberately does not use
    # LLM_PROVIDER/Anthropic (see CLAUDE.md). config.gemini_api_key/model are
    # populated unconditionally from GEMINI_API_KEY/GEMINI_MODEL regardless
    # of what LLM_PROVIDER is set to, so this is never accidentally paired
    # with another provider's credentials.
    llm = LLMClient("gemini", config.gemini_api_key, config.gemini_model)

    label_id = gmail_client.get_or_create_label(gmail, JOB_BOT_LABEL_NAME)
    thread_ids = gmail_client.search_candidate_threads(
        gmail, config.max_emails_per_run, exclude_label=JOB_BOT_LABEL_NAME
    )
    logger.info("Found %d candidate thread(s) to check", len(thread_ids))

    outcomes: list[ThreadOutcome] = []
    failure_count = 0
    for thread_id in thread_ids:
        try:
            outcome = _process_thread(gmail, notion, llm, thread_id, label_id)
            if outcome:
                outcomes.append(outcome)
        except Exception:
            failure_count += 1
            logger.exception("Failed processing thread %s; will retry next run", thread_id)

    if failure_count:
        logger.warning("%d of %d thread(s) failed this run", failure_count, len(thread_ids))
    # If every single candidate failed, this is very unlikely to be a batch
    # of unrelated per-email flukes -- it's much more likely a systemic
    # problem (bad credentials, wrong Notion database id, etc). Fail the run
    # loudly so GitHub Actions reports it as failed.
    if thread_ids and failure_count == len(thread_ids):
        raise RuntimeError(
            f"All {failure_count} candidate thread(s) failed to process -- "
            "likely a systemic issue (credentials, Notion database id, etc), "
            "not per-email flukes. See exception logs above for the root cause."
        )

    review = _daily_career_review(notion)
    brief_text = _compose_morning_brief(outcomes, review, had_candidates=bool(thread_ids))
    logger.info("\n%s", brief_text)

    try:
        today = datetime.date.today().isoformat()
        notion.create_page_with_body(
            config.notion_morning_brief_database_id,
            {"Name": notion_client.title_prop(f"Morning Brief — {today}"), "Date": notion_client.date_prop(today)},
            brief_text,
        )
    except Exception:
        logger.exception("Failed to write Morning Brief to Notion -- see log output above for its content")


def _process_thread(gmail, notion, llm, thread_id: str, label_id: str) -> ThreadOutcome | None:
    thread = gmail_client.get_thread(gmail, thread_id)
    existing_page = notion.find_page_by_thread_id(thread_id)
    if existing_page and existing_page.last_processed_message_id == thread.message_id:
        logger.info("Thread %s already processed, skipping", thread_id)
        return None

    email_text = _email_context(thread)

    try:
        if not llm.is_job_related(email_text):
            logger.info("Thread %s judged not job-related, skipping", thread_id)
            _apply_label_best_effort(gmail, thread_id, label_id)
            return None
        analysis = llm.analyze_email(email_text)
    except LLMProviderError:
        logger.exception(
            "LLM provider failed for thread %s; flagging for manual review", thread_id
        )
        properties = _build_needs_review_notion_properties(thread, is_new_row=existing_page is None)
        if existing_page:
            notion.update_page(existing_page.page_id, properties)
        else:
            existing_page = _PageRef(notion.create_page(properties))
        note = f"{datetime.date.today().isoformat()}: LLM provider failed -- needs manual review."
        notion.append_note(existing_page.page_id, note)
        logger.info("Thread %s logged with status '%s'", thread_id, NEEDS_AI_REVIEW_STATUS)
        # Deliberately not labeled -- see _build_needs_review_notion_properties.
        return None

    logger.info("Thread %s classified as %s", thread_id, analysis.classification)

    if existing_page is None and analysis.company:
        existing_page = notion.find_page_by_company(analysis.company)

    contact = _contact_name(analysis.contact_name, analysis.company, thread.sender_name)
    is_new_row = existing_page is None
    properties = _build_notion_properties(thread, analysis, contact, is_new_row)

    if existing_page:
        notion.update_page(existing_page.page_id, properties)
        page_id = existing_page.page_id
    else:
        page_id = notion.create_page(properties)

    note_lines = [
        f"{datetime.date.today().isoformat()}: {analysis.summary}",
        f"Replied already: {'Yes' if thread.already_replied else 'No'}",
    ]
    if analysis.legitimacy_notes:
        note_lines.append(f"Legitimacy notes: {analysis.legitimacy_notes}")
    if thread.attachment_names:
        note_lines.append(f"Attachments: {', '.join(thread.attachment_names)}")
    notion.append_note(page_id, "\n".join(note_lines))

    if not thread.already_replied:
        try:
            gmail_client.create_draft_reply(gmail, thread, analysis.suggested_reply)
        except Exception:
            logger.warning("Failed to create Gmail draft for thread %s; continuing", thread_id, exc_info=True)

    _apply_label_best_effort(gmail, thread_id, label_id)

    logger.info("Thread %s processed: CRM updated", thread_id)
    return ThreadOutcome(
        company=analysis.company or "Unknown Company",
        role=analysis.role,
        contact=contact,
        classification=analysis.classification,
        priority=analysis.priority,
        next_action=analysis.next_action,
        legitimacy_confidence=analysis.legitimacy_confidence,
        legitimacy_notes=analysis.legitimacy_notes,
        thread_link=gmail_client.thread_link(thread.thread_id),
    )


@dataclass
class _PageRef:
    """Minimal stand-in for notion_client.ExistingPage when a brand-new page
    was just created and we only have its id (no stored message-id yet)."""

    page_id: str
    last_processed_message_id: str = ""


@dataclass
class _CareerReviewItem:
    name: str
    company: str
    stage: str
    status: str
    priority: str
    follow_up_date: str | None
    date_received: str | None
    next_step: str
    days_overdue: int = 0


@dataclass
class CareerReview:
    overdue_followups: list[_CareerReviewItem] = field(default_factory=list)
    waiting_too_long: list[_CareerReviewItem] = field(default_factory=list)
    upcoming_interviews: list[_CareerReviewItem] = field(default_factory=list)


def _daily_career_review(notion: notion_client.NotionClient) -> CareerReview:
    today = datetime.date.today()
    pages = notion.query_pages({"property": "Archived", "checkbox": {"equals": False}})

    review = CareerReview()
    for page in pages:
        stage = notion_client.plain_select(page, "Stage")
        status = notion_client.plain_select(page, "Status")
        if stage in _CLOSED_STAGES or status in _CLOSED_STATUSES:
            continue

        item = _CareerReviewItem(
            name=notion_client.plain_rich_text(page, "Name")
            or page.get("properties", {}).get("Name", {}).get("title", [{}])[0].get("plain_text", ""),
            company=notion_client.plain_rich_text(page, "Company"),
            stage=stage,
            status=status,
            priority=notion_client.plain_select(page, "Priority"),
            follow_up_date=notion_client.plain_date(page, "Follow-up Date") or notion_client.plain_date(page, "Follow-up"),
            date_received=notion_client.plain_date(page, "Date Received"),
            next_step=notion_client.plain_rich_text(page, "Next Step"),
        )

        if item.follow_up_date:
            follow_up = datetime.date.fromisoformat(item.follow_up_date[:10])
            if follow_up <= today:
                item.days_overdue = (today - follow_up).days
                review.overdue_followups.append(item)

        if item.date_received:
            received = datetime.date.fromisoformat(item.date_received[:10])
            if (today - received).days > _WAITING_TOO_LONG_DAYS:
                review.waiting_too_long.append(item)

        interview_date = notion_client.plain_date(page, "Interview Date")
        if interview_date:
            interview = datetime.date.fromisoformat(interview_date[:10])
            if interview >= today:
                review.upcoming_interviews.append(item)

    review.overdue_followups.sort(key=lambda i: i.days_overdue, reverse=True)
    return review


def _compose_morning_brief(outcomes: list[ThreadOutcome], review: CareerReview, had_candidates: bool) -> str:
    lines = ["🌅 Morning Job Brief", ""]

    if not had_candidates:
        lines.append("No new job emails.")
    else:
        lines.append(f"New recruitment emails: {len(outcomes)}")
        for o in outcomes:
            lines.append(
                f"  - {o.company} ({o.role or 'role unclear'}): {o.classification}, "
                f"priority {o.priority} -- {o.thread_link}"
            )

    lines.append("")
    needing_reply = [o for o in outcomes if o.next_action.strip().lower() not in ("no action required", "wait for recruiter")]
    lines.append(f"Applications needing a reply today: {len(needing_reply)}")
    for o in needing_reply:
        lines.append(f"  - {o.company}: {o.next_action}")

    lines.append("")
    interviews_assessments = [
        o for o in outcomes if o.classification in ("Interview invitation", "Case study or assessment")
    ]
    lines.append(f"Interviews/assessments needing attention: {len(interviews_assessments)}")
    for o in interviews_assessments:
        lines.append(f"  - {o.company}: {o.classification} -- {o.next_action}")
    for item in review.upcoming_interviews:
        lines.append(f"  - {item.company or item.name}: interview/assessment coming up")

    lines.append("")
    lines.append(
        f"Follow-ups due today or overdue: {len(review.overdue_followups)} "
        f"(showing top {min(_MAX_PRIORITY_ACTIONS, len(review.overdue_followups))})"
    )
    for item in review.overdue_followups[:_MAX_PRIORITY_ACTIONS]:
        lines.append(f"  - {item.company or item.name}: {item.days_overdue} day(s) overdue -- {item.next_step}")

    lines.append("")
    lines.append(f"Applications waiting >{_WAITING_TOO_LONG_DAYS} days without a response: {len(review.waiting_too_long)}")

    lines.append("")
    suspicious = [o for o in outcomes if o.legitimacy_confidence != "High confidence genuine"]
    lines.append(f"Suspicious or scam emails: {len(suspicious)}")
    for o in suspicious:
        lines.append(f"  - {o.company}: {o.legitimacy_confidence} -- {o.legitimacy_notes or 'no details'}")

    lines.append("")
    lines.append("Recommended priorities (max 5):")
    priorities = _rank_priority_actions(outcomes, review)
    for i, action in enumerate(priorities[:_MAX_PRIORITY_ACTIONS], start=1):
        lines.append(f"{i}. {action}")
    if not priorities:
        lines.append("Nothing urgent -- you're caught up.")

    return "\n".join(lines)


def _rank_priority_actions(outcomes: list[ThreadOutcome], review: CareerReview) -> list[str]:
    urgent_order = {"Urgent": 0, "High": 1, "Normal": 2, "Low": 3}
    actions = []

    for o in sorted(outcomes, key=lambda o: urgent_order.get(o.priority, 2)):
        if o.next_action.strip().lower() not in ("no action required", "wait for recruiter"):
            actions.append(f"{o.next_action} ({o.company})")

    for item in review.overdue_followups:
        actions.append(f"Follow up with {item.company or item.name} ({item.days_overdue}d overdue)")

    return actions


if __name__ == "__main__":
    run()
