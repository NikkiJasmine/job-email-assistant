import base64
import datetime
from unittest.mock import MagicMock

from src.story_scout.models import RawStory, ScoutedStory, StoryPackage
from src.story_scout.notifier import send_digest_email


def _scouted_story(title="A story", url="https://a.com/1"):
    raw = RawStory(
        source_name="Adweek",
        category="Advertising",
        title=title,
        url=url,
        published_at=datetime.date(2026, 7, 1),
        text=title,
    )
    package = StoryPackage(
        summary="A summary.",
        key_lessons="Lead with the data.",
        linkedin_post_ideas=["Hook one.", "Hook two.", "Hook three."],
    )
    return ScoutedStory(raw=raw, package=package)


def test_send_digest_email_does_nothing_for_no_stories():
    service = MagicMock()
    send_digest_email(service, "me@example.com", [])
    service.users().messages().send.assert_not_called()


def test_send_digest_email_sends_one_message_with_all_stories():
    service = MagicMock()
    stories = [_scouted_story("First story", "https://a.com/1"), _scouted_story("Second story", "https://a.com/2")]

    send_digest_email(service, "me@example.com", stories)

    service.users().messages().send.assert_called_once()
    _, kwargs = service.users().messages().send.call_args
    raw = base64.urlsafe_b64decode(kwargs["body"]["raw"]).decode("utf-8")

    assert "me@example.com" in raw
    assert "First story" in raw
    assert "Second story" in raw
    assert "Hook one." in raw
