"""YouTube implementation of the Source protocol.

Uses the official YouTube Data API v3 (a plain API key, no OAuth) to search
for recent marketing-related videos and, for the final top stories, pull
real top comments for the "public reaction" writeup.
"""

import datetime
import logging

import httpx

from src.story_scout.models import RawStory

logger = logging.getLogger("story_scout.sources.youtube")

_API_BASE = "https://www.googleapis.com/youtube/v3"
_MAX_RESULTS_PER_QUERY = 10
_MAX_COMMENTS = 10

SEARCH_QUERIES = [
    "marketing campaign",
    "ad campaign backlash",
    "rebrand reaction",
    "viral marketing campaign",
    "influencer marketing",
]


class YouTubeSource:
    name = "YouTube"

    def __init__(self, api_key: str, queries: list[str] | None = None):
        self._api_key = api_key
        self._queries = queries if queries is not None else SEARCH_QUERIES

    def fetch_recent(self, since: datetime.date) -> list[RawStory]:
        stories = []
        for query in self._queries:
            try:
                stories.extend(self._search(query, since))
            except Exception:
                logger.exception("Failed searching YouTube for %r; skipping this query", query)
        return stories

    def _search(self, query: str, since: datetime.date) -> list[RawStory]:
        response = httpx.get(
            f"{_API_BASE}/search",
            params={
                "key": self._api_key,
                "q": query,
                "part": "snippet",
                "type": "video",
                "order": "relevance",
                "maxResults": _MAX_RESULTS_PER_QUERY,
                "publishedAfter": f"{since.isoformat()}T00:00:00Z",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        video_ids = [
            item["id"]["videoId"] for item in response.json().get("items", []) if item.get("id", {}).get("videoId")
        ]
        if not video_ids:
            return []
        return self._stats(video_ids)

    def _stats(self, video_ids: list[str]) -> list[RawStory]:
        response = httpx.get(
            f"{_API_BASE}/videos",
            params={"key": self._api_key, "id": ",".join(video_ids), "part": "snippet,statistics"},
            timeout=15.0,
        )
        response.raise_for_status()

        stories = []
        for item in response.json().get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            video_id = item.get("id")
            title = snippet.get("title")
            if not title or not video_id:
                continue

            stories.append(
                RawStory(
                    source_name=snippet.get("channelTitle", "YouTube"),
                    platform="YouTube",
                    title=title,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    published_at=_video_date(snippet.get("publishedAt")),
                    text=f"{title}\n\n{snippet.get('description', '')}",
                    engagement_note=f"{stats.get('viewCount', '0')} views - {stats.get('commentCount', '0')} comments",
                    fetch_comments=lambda vid=video_id: self._fetch_comments(vid),
                )
            )
        return stories

    def _fetch_comments(self, video_id: str) -> str:
        try:
            response = httpx.get(
                f"{_API_BASE}/commentThreads",
                params={
                    "key": self._api_key,
                    "videoId": video_id,
                    "part": "snippet",
                    "order": "relevance",
                    "maxResults": _MAX_COMMENTS,
                    "textFormat": "plainText",
                },
                timeout=15.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError:
            # Comments can be disabled on a video -- that's not a run failure.
            return ""

        comments = []
        for item in response.json().get("items", []):
            text = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {}).get("textDisplay")
            if text:
                comments.append(text.strip())
        return "\n\n".join(comments[:_MAX_COMMENTS])


def _video_date(published_at: str | None) -> datetime.date | None:
    if not published_at:
        return None
    return datetime.datetime.strptime(published_at[:10], "%Y-%m-%d").date()
