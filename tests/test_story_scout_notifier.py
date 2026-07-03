import base64
import datetime
from unittest.mock import MagicMock

from src.story_scout.models import RawStory, ScoutedStory, StoryPackage
from src.story_scout.notifier import send_digest_email


def _scouted_story(title="A story", url="https://a.com/1"):
    raw = RawStory(
        source_name="Adweek",
        platform="RSS",
        title=title,
        url=url,
        published_at=datetime.date(2026, 7, 1),
        text=title,
    )
    package = StoryPackage(
        brand="Brand A",
        topic="Rebrands",
        summary="A summary.",
        why_it_matters="It matters.",
        public_reaction="Mixed reactions.",
        marketing_lesson="Lead with the data.",
        linkedin_post_angles=["Angle one.", "Angle two.", "Angle three."],
        score=9,
        score_reason="Original and widely discussed.",
    )
    return ScoutedStory(raw=raw, package=package)


def test_send_digest_email_does_nothing_for_no_stories():
    service = MagicMock()
    send_digest_email(service, "me@example.com", "a report", [])
    service.users().messages().send.assert_not_called()


def test_send_digest_email_sends_the_report_text():
    service = MagicMock()
    stories = [_scouted_story()]

    send_digest_email(service, "me@example.com", "the full report body", stories)

    service.users().messages().send.assert_called_once()
    _, kwargs = service.users().messages().send.call_args
    raw = base64.urlsafe_b64decode(kwargs["body"]["raw"]).decode("utf-8")

    assert "me@example.com" in raw
    assert "the full report body" in raw
