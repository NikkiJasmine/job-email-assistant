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
