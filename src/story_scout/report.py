"""Builds the narrative digest report: a top-story callout, the remaining
stories in ranked order, and a closing "Patterns I'm noticing" section.
"""

from src.story_scout.models import ScoutedStory


def _story_block(rank: int, story: ScoutedStory) -> str:
    raw, package = story.raw, story.package
    angles = "\n".join(f"  {i + 1}. {angle}" for i, angle in enumerate(package.linkedin_post_angles))
    score_line = f"Score: {package.score}/10\n" if package.score is not None else ""
    return (
        f"{rank}. {raw.title} ({package.brand})\n"
        f"{raw.url}\n"
        f"{raw.source_name} | {raw.platform} | {package.topic}\n"
        f"{score_line}\n"
        f"Summary: {package.summary}\n\n"
        f"Why it matters: {package.why_it_matters}\n\n"
        f"Public reaction: {package.public_reaction}\n\n"
        f"Marketing lesson: {package.marketing_lesson}\n\n"
        f"LinkedIn post angles:\n{angles}"
    )


def build_report(recipient_name: str, stories: list[ScoutedStory], patterns: str) -> str:
    if not stories:
        return ""

    top, rest = stories[0], stories[1:]

    sections = [
        "⭐ Story Scout AI",
        f"If {recipient_name} only reads one story today, read this first.",
        f"Why this is the top story: {top.package.score_reason}",
        _story_block(1, top),
    ]
    sections.extend(_story_block(rank, story) for rank, story in enumerate(rest, start=2))
    sections.append(
        "Patterns I'm noticing\n"
        + (patterns or "Not enough of a throughline across today's stories to call out a pattern.")
    )

    return "\n\n---\n\n".join(sections)
