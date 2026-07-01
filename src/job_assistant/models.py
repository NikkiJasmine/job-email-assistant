"""Shared constants for the job-assistant pipeline."""

TRACK = "Applications"
CATEGORY = "Recruiter"

# Initial Stage value implied by a classification. None means "leave Stage
# unchanged on update, or default to Applied on create" -- see main.py.
# Deliberately no mapping to Offer/Closed: those are always set manually.
STAGE_MAPPING: dict[str, str | None] = {
    "Interview Invitation": "Interviewing",
    "Rejection": "Rejected",
    "Assessment": "Case Study",
    "Next Step": None,
    "Request for Information": None,
}

DEFAULT_STAGE_FOR_NEW_ROW = "Applied"

# Status set on a row when the configured LLM provider fails (outage, no
# credits, invalid key, rate limit, etc) instead of a real classification --
# see job_assistant/main.py. Must be added as a Status select option in
# Notion alongside the CLASSIFICATIONS values.
NEEDS_AI_REVIEW_STATUS = "Needs AI Review"
