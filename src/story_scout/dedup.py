"""Removes duplicate stories within a single run's candidate pool.

Two passes, both stdlib-only:
1. Exact match on a canonicalized URL (strips query/tracking params,
   lowercases the host, drops a trailing slash).
2. Near-duplicate titles (the same press release/story picked up
   near-verbatim by two outlets), via difflib.SequenceMatcher on normalized
   titles.

Known limitation: outlets that cover the same underlying news with very
different headlines won't be caught by pass 2 -- acceptable for v1; a
semantic/LLM-based clustering pass is a natural upgrade if it matters later.
"""

import difflib
import re
from urllib.parse import urlsplit, urlunsplit

from src.story_scout.models import RawStory

_TITLE_SIMILARITY_THRESHOLD = 0.85


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def remove_duplicates(stories: list[RawStory]) -> list[RawStory]:
    seen_urls: set[str] = set()
    kept: list[RawStory] = []
    kept_titles: list[str] = []

    for story in stories:
        canonical = _canonical_url(story.url)
        if canonical in seen_urls:
            continue

        normalized_title = _normalize_title(story.title)
        if any(
            difflib.SequenceMatcher(None, normalized_title, kept_title).ratio() > _TITLE_SIMILARITY_THRESHOLD
            for kept_title in kept_titles
        ):
            continue

        seen_urls.add(canonical)
        kept_titles.append(normalized_title)
        kept.append(story)

    return kept
