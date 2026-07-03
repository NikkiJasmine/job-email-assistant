"""Sends a digest email of the stories Story Scout added to Notion this run.

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


def _story_section(story: ScoutedStory) -> str:
    raw, package = story.raw, story.package
    ideas = "\n".join(f"  {i + 1}. {idea}" for i, idea in enumerate(package.linkedin_post_ideas))
    return (
        f"{raw.title}\n"
        f"{raw.url}\n"
        f"{raw.source_name} | {raw.category}\n\n"
        f"Summary: {package.summary}\n\n"
        f"Key lessons: {package.key_lessons}\n\n"
        f"LinkedIn post ideas:\n{ideas}"
    )


def send_digest_email(service, to_email: str, stories: list[ScoutedStory]) -> None:
    """Sends one email listing every story added this run. No-op if none were added."""
    if not stories:
        return

    subject = f"Story Scout: {len(stories)} new stor{'y' if len(stories) == 1 else 'ies'} for LinkedIn"
    body = "\n\n---\n\n".join(_story_section(story) for story in stories)

    message = MIMEText(body)
    message["to"] = to_email
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
