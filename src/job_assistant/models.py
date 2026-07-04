"""Shared constants for the Morning Job Brief pipeline."""

TRACK = "Applications"
CATEGORY = "Recruiter"

# Gmail label applied to every thread this pipeline has processed (created if
# missing on first run). This is the *primary* dedup mechanism -- a single
# Gmail search filter (-label:Job-Bot-Processed) excludes anything already
# handled, regardless of what ended up in Notion. See gmail_client.py.
JOB_BOT_LABEL_NAME = "Job-Bot-Processed"

# Stage values this pipeline sets, keyed by classification. None means "leave
# Stage unchanged on update, or default to Applied on create" -- see main.py.
# Deliberately no mapping to Offer/Closed: those are always set manually.
STAGE_MAPPING: dict[str, str | None] = {
    "Interview invitation": "Interviewing",
    "Rejection": "Rejected",
    "Case study or assessment": "Case Study",
    "Good news": None,
    "Request for more information": None,
    "Another next step": None,
}

DEFAULT_STAGE_FOR_NEW_ROW = "Applied"

# Status set on a row when the configured LLM provider fails (outage, no
# credits, invalid key, rate limit, etc) instead of a real classification.
# Deliberately outside CONVERSATION_STATUSES below: this is a self-healing
# retry marker (the row gets no Last Processed Message ID, so it's retried
# next run), not a conversation state -- and it's already a pre-existing
# Status option in the CRM.
NEEDS_AI_REVIEW_STATUS = "Needs AI Review"

# The only Status values this pipeline writes for a resolved thread, per the
# Morning Job Brief spec. Tracks conversation state -- distinct from Stage
# (pipeline phase, above) and from classification (what kind of email it
# was, folded into the Email Summary text rather than its own property).
CONVERSATION_STATUSES = ["Active", "Messaged", "Call Scheduled", "Closed", "Followed Up"]


def determine_status(classification: str, already_replied: bool, next_action: str) -> str:
    """Maps a classification + conversation state to one of CONVERSATION_STATUSES.

    Deliberately simple: this pipeline only ever sees inbound recruiter
    email, so "Messaged" (an outbound-initiated conversation) doesn't arise
    here -- that status is set by the separate Outreach Agent / Career CRM
    Agent flow instead.
    """
    if next_action.strip().lower() == "no action required" or classification == "Rejection":
        return "Closed"
    if classification == "Interview invitation" and already_replied:
        return "Call Scheduled"
    if already_replied:
        return "Followed Up"
    return "Active"
