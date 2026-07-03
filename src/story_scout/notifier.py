"""Sends the Story Scout digest report email.

Reuses src/common/gmail_client.build_service for OAuth setup only. Unlike
that module, this one does call a send-capable Gmail API method
(users.messages.send) -- deliberately: this always sends a summary to the
user's own inbox (self-notification), never a message to a third party on
the user's behalf. That's a materially different, much lower-risk action
than the Job Email Assistant's "never auto-send a reply" guarantee, which
common/gmail_client.py intentionally does not implement (see that file's
module docstring). Keep send-capable code confined to this file.
"""

import base64
from email.mime.text import MIMEText

from src.story_scout.models import ScoutedStory


def send_digest_email(service, to_email: str, report_text: str, stories: list[ScoutedStory]) -> None:
    """Sends the digest report. No-op if there are no stories to report."""
    if not stories:
        return

    subject = f"Story Scout: top {len(stories)} stor{'y' if len(stories) == 1 else 'ies'} for LinkedIn"

    message = MIMEText(report_text)
    message["to"] = to_email
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
