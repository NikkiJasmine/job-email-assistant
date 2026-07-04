"""Gmail API wrapper: search, read, label, and draft-reply on threads.

Scope used: gmail.modify. This is a superset of the previously-used
gmail.readonly + gmail.compose, needed because the Morning Job Brief
pipeline's primary dedup mechanism is a Gmail label (Job-Bot-Processed) --
listing/creating labels and applying them to a thread requires gmail.modify
(gmail.labels alone only covers managing label *definitions*, not applying
them to messages/threads).

This module still intentionally never implements or calls any send-capable
method (users.messages.send, users.drafts.send) -- that remains the
structural safeguard against ever sending email automatically. gmail.modify
technically permits drafts.create/update (not send), so the "never send"
guarantee comes from this file simply not containing that call, not from
the OAuth scope alone. Do not add a send function here.
"""

import base64
import logging
from dataclasses import dataclass, field
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


@dataclass
class EmailThread:
    thread_id: str
    message_id: str  # Gmail message id of the last *inbound* message -- used as the dedup marker
    rfc_message_id: str  # RFC822 Message-ID header, needed for In-Reply-To/References
    subject: str
    sender_name: str
    sender_email: str
    body_text: str
    already_replied: bool  # True if the newest message in the thread was sent by the candidate
    attachment_names: list[str] = field(default_factory=list)


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


def search_candidate_threads(service, max_results: int, exclude_label: str | None = None) -> list[str]:
    """Returns thread IDs from the last 2 days, optionally excluding a label.

    Deliberately a plain time(+label) filter rather than a keyword-boolean
    query -- in practice a keyword query both misses genuine recruiter
    threads (subject lines rarely match a fixed list) and still lets spam
    through, so relevance is judged per-thread instead (see job_assistant/
    main.py), not pre-filtered by search terms.
    """
    query = "newer_than:2d in:inbox"
    if exclude_label:
        query += f" -label:{exclude_label}"

    response = (
        service.users()
        .threads()
        .list(userId="me", q=query, maxResults=max_results)
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


def _attachment_names(payload: dict) -> list[str]:
    names = []
    if payload.get("filename"):
        names.append(payload["filename"])
    for part in payload.get("parts", []) or []:
        names.extend(_attachment_names(part))
    return names


def get_thread(service, thread_id: str) -> EmailThread:
    """Reads a thread, analyzing the last *inbound* message rather than
    unconditionally the last message overall -- if Nicole has already
    replied, the literal last message is her own text, not the recruiter's,
    which would otherwise get summarized/classified as if it were their
    email. `already_replied` reflects whether an even-newer outbound message
    exists after that last inbound one (i.e. the thread's true last message
    carries the SENT label).
    """
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    messages = thread["messages"]
    last_message = messages[-1]
    last_inbound = next(
        (m for m in reversed(messages) if "SENT" not in m.get("labelIds", [])), last_message
    )
    already_replied = "SENT" in last_message.get("labelIds", [])

    headers = last_inbound["payload"]["headers"]
    from_header = _header(headers, "From")
    sender_name, sender_email = from_header, from_header
    if "<" in from_header and ">" in from_header:
        sender_name = from_header.split("<")[0].strip().strip('"')
        sender_email = from_header.split("<")[1].split(">")[0].strip()

    return EmailThread(
        thread_id=thread_id,
        message_id=last_inbound["id"],
        rfc_message_id=_header(headers, "Message-ID"),
        subject=_header(headers, "Subject"),
        sender_name=sender_name or sender_email,
        sender_email=sender_email,
        body_text=_decode_body(last_inbound["payload"]),
        already_replied=already_replied,
        attachment_names=_attachment_names(last_inbound["payload"]),
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


def list_labels(service) -> dict[str, str]:
    """Returns a {name: label_id} mapping of the account's Gmail labels."""
    response = service.users().labels().list(userId="me").execute()
    return {label["name"]: label["id"] for label in response.get("labels", [])}


def get_or_create_label(service, name: str) -> str:
    """Returns the id of the given label, creating it (as a user label) if missing."""
    labels = list_labels(service)
    if name in labels:
        return labels[name]

    created = (
        service.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )
    return created["id"]


def apply_label(service, thread_id: str, label_id: str) -> None:
    """Applies a label to every message in a thread. Best-effort by design --
    callers should catch failures, log a warning, and continue rather than
    let a labeling failure block the rest of the pipeline (see
    job_assistant/main.py)."""
    service.users().threads().modify(
        userId="me", id=thread_id, body={"addLabelIds": [label_id]}
    ).execute()
