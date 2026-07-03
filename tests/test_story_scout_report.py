import datetime

from src.story_scout.models import RawStory, ScoutedStory, StoryPackage
from src.story_scout.report import build_report


def _scouted_story(title, score, score_reason=""):
    raw = RawStory(
        source_name="Adweek",
        platform="RSS",
        title=title,
        url=f"https://a.com/{title}",
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
        score=score,
        score_reason=score_reason,
    )
    return ScoutedStory(raw=raw, package=package)


def test_build_report_returns_empty_string_for_no_stories():
    assert build_report("Nicole", [], "") == ""


def test_build_report_leads_with_top_story_and_recipient_name():
    stories = [_scouted_story("Top story", 9, "It's the most original take this week.")]

    text = build_report("Nicole", stories, "")

    assert text.startswith("⭐ Story Scout AI")
    assert "If Nicole only reads one story today, read this first." in text
    assert "It's the most original take this week." in text
    assert "Top story" in text


def test_build_report_includes_all_stories_in_order():
    stories = [_scouted_story("First", 9), _scouted_story("Second", 8), _scouted_story("Third", 7)]

    text = build_report("Nicole", stories, "")

    assert text.index("First") < text.index("Second") < text.index("Third")


def test_build_report_appends_patterns_section():
    stories = [_scouted_story("Only story", 9)]

    text = build_report("Nicole", stories, "Three brands leaned on nostalgia this week.")

    assert "Patterns I'm noticing" in text
    assert "Three brands leaned on nostalgia this week." in text


def test_build_report_notes_when_no_pattern_found():
    stories = [_scouted_story("Only story", 9)]

    text = build_report("Nicole", stories, "")

    assert "Patterns I'm noticing" in text
    assert "Not enough of a throughline" in text
