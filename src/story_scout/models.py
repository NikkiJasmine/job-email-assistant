"""Data models shared across the Story Scout AI pipeline stages."""

import datetime
from dataclasses import dataclass


@dataclass
class RawStory:
    source_name: str
    category: str
    title: str
    url: str
    published_at: datetime.date | None
    text: str  # title + feed summary/description, used as LLM input


@dataclass
class StoryPackage:
    summary: str
    key_lessons: str
    linkedin_post_ideas: list[str]


@dataclass
class ScoutedStory:
    raw: RawStory
    package: StoryPackage
