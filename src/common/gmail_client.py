"""Gmail API wrapper: search, read, and draft-reply on threads.

Scopes used: gmail.readonly + gmail.compose only. This module intentionally
never implements or calls any send-capable method (users.messages.send,
users.drafts.send) -- that is the structural safeguard against ever sending
email automatically. gmail.compose technically permits drafts.send, so the
"never send" guarantee comes from this file simply not containing that call,
not from the OAuth scope alone. Do not add a send function here.

Deliberately no label-based dedup here: creating/reading Gmail labels
requires the gmail.labels or gmail.modify scope, which we don't request to
keep the OAuth scope minimal. Dedup is instead tracked in Notion (see
notion_client.find_page_by_thread_id and job_assistant/main.py), by
comparing each thread's latest message id against a stored
"Last Processed Message ID" property.
"""

import base64
from dataclasses import dataclass
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

SEARCH_QUERY = (
    '(recruiter OR recruiting OR "job opportunity" OR interview OR position '
    'OR candidate OR hiring OR application OR "hiring manager" OR '
    '"next steps" OR assessment) '
    "newer_than:2d in:inbox"
)


@dataclass
class EmailThread:
    thread_id: str
    message_id: str  # Gmail message id of the last message, used for reply headers
    rfc_message_id: str  # RFC822 Message-ID header, needed for In-Reply-To/References
    subject: str
    sender_name: str
    sender_email: str
    body_text: str


def build_service(client_id: str, client_secret: str, refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def search_candidate_threads(service, max_results: int) -> list[str]:
    """Returns thread IDs matching the job/recruiter heuristic.

    Does not exclude already-processed threads -- that check happens later,
    cheaply, against Notion (see job_assistant/main.py), before any LLM call.
    """
    response = (
        service.users()
        .threads()
        .list(userId="me", q=SEARCH_QUERY, maxResults=max_results)
        .execute()
    )
    return [t["id"] for t in response.get("threads", [])]


def _decode_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []) or []:
        text = _decode_body(part)
        if text:
            return text
    return ""


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def get_thread(service, thread_id: str) -> EmailThread:
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    last_message = thread["messages"][-1]
    headers = last_message["payload"]["headers"]

    from_header = _header(headers, "From")
    sender_name, sender_email = from_header, from_header
    if "<" in from_header and ">" in from_header:
        sender_name = from_header.split("<")[0].strip().strip('"')
        sender_email = from_header.split("<")[1].split(">")[0].strip()

    return EmailThread(
        thread_id=thread_id,
        message_id=last_message["id"],
        rfc_message_id=_header(headers, "Message-ID"),
        subject=_header(headers, "Subject"),
        sender_name=sender_name or sender_email,
        sender_email=sender_email,
        body_text=_decode_body(last_message["payload"]),
    )


def create_draft_reply(service, thread: EmailThread, reply_body: str) -> str:
    """Creates a Gmail draft reply on the given thread. Never sends it."""
    subject = thread.subject if thread.subject.lower().startswith("re:") else f"Re: {thread.subject}"

    message = MIMEText(reply_body)
    message["to"] = thread.sender_email
    message["subject"] = subject
    if thread.rfc_message_id:
        message["In-Reply-To"] = thread.rfc_message_id
        message["References"] = thread.rfc_message_id

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw, "threadId": thread.thread_id}})
        .execute()
    )
    return draft["id"]


def thread_link(thread_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#all/{thread_id}"
