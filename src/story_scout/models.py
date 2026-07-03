"""Data models shared across the Story Scout AI pipeline stages."""

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class RawStory:
    source_name: str  # specific outlet/subreddit/channel, e.g. "r/marketing", "Adweek"
    platform: str  # "RSS", "Reddit", "YouTube" (manual entries may set "Instagram", "TikTok", "LinkedIn", ...)
    title: str
    url: str
    published_at: datetime.date | None
    text: str  # title + description/snippet, used as LLM input
    engagement_note: str = ""  # e.g. "1.2k upvotes - 340 comments", empty when unknown
    # Only set by sources that can fetch real comment text (Reddit, YouTube).
    # Called at most once, only for stories that make the final top-N cut, to
    # avoid an extra API call per candidate.
    fetch_comments: Callable[[], str] | None = field(default=None, repr=False, compare=False)


@dataclass
class StoryPackage:
    brand: str
    topic: str
    summary: str
    why_it_matters: str
    public_reaction: str
    marketing_lesson: str
    linkedin_post_angles: list[str]
    score: int | None = None
    score_reason: str = ""


@dataclass
class ScoutedStory:
    raw: RawStory
    package: StoryPackage
