"""Reddit implementation of the Source protocol.

Uses Reddit's OAuth2 client_credentials grant (a "userless"/app-only access
token) to read public subreddit listings and comments -- no Reddit user
account needed, just a free "script" app registered at
reddit.com/prefs/apps. This is Reddit's own supported way to make read-only
API requests without a logged-in user, not a workaround.
"""

import datetime
import logging

import httpx

from src.story_scout.models import RawStory

logger = logging.getLogger("story_scout.sources.reddit")

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API_BASE = "https://oauth.reddit.com"
_USER_AGENT = "story-scout-ai/1.0 (script; read-only)"
_MAX_POSTS_PER_SUBREDDIT = 10
_MAX_COMMENTS = 10

TRUSTED_SUBREDDITS = [
    "marketing",
    "advertising",
    "socialmedia",
    "DigitalMarketing",
    "PublicRelations",
]


class RedditSource:
    name = "Reddit"

    def __init__(self, client_id: str, client_secret: str, subreddits: list[str] | None = None):
        self._client_id = client_id
        self._client_secret = client_secret
        self._subreddits = subreddits if subreddits is not None else TRUSTED_SUBREDDITS
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        response = httpx.post(
            _TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
            headers={"User-Agent": _USER_AGENT},
            timeout=15.0,
        )
        response.raise_for_status()
        self._token = response.json()["access_token"]
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}", "User-Agent": _USER_AGENT}

    def fetch_recent(self, since: datetime.date) -> list[RawStory]:
        stories = []
        for subreddit in self._subreddits:
            try:
                stories.extend(self._fetch_subreddit(subreddit, since))
            except Exception:
                logger.exception("Failed fetching r/%s; skipping this subreddit", subreddit)
        return stories

    def _fetch_subreddit(self, subreddit: str, since: datetime.date) -> list[RawStory]:
        response = httpx.get(
            f"{_API_BASE}/r/{subreddit}/top",
            params={"t": "week", "limit": _MAX_POSTS_PER_SUBREDDIT},
            headers=self._headers(),
            timeout=15.0,
        )
        response.raise_for_status()

        stories = []
        for child in response.json().get("data", {}).get("children", []):
            post = child.get("data", {})
            published = _post_date(post)
            if published is not None and published < since:
                continue
            title = post.get("title")
            permalink = post.get("permalink")
            post_id = post.get("id")
            if not title or not permalink or not post_id:
                continue

            stories.append(
                RawStory(
                    source_name=f"r/{subreddit}",
                    platform="Reddit",
                    title=title,
                    url=f"https://www.reddit.com{permalink}",
                    published_at=published,
                    text=f"{title}\n\n{post.get('selftext', '')}",
                    engagement_note=f"{post.get('score', 0)} upvotes - {post.get('num_comments', 0)} comments",
                    fetch_comments=lambda pid=post_id, sub=subreddit: self._fetch_comments(sub, pid),
                )
            )
        return stories

    def _fetch_comments(self, subreddit: str, post_id: str) -> str:
        response = httpx.get(
            f"{_API_BASE}/r/{subreddit}/comments/{post_id}",
            params={"limit": _MAX_COMMENTS, "sort": "top"},
            headers=self._headers(),
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        if len(payload) < 2:
            return ""

        comments = []
        for child in payload[1].get("data", {}).get("children", []):
            body = child.get("data", {}).get("body")
            if body:
                comments.append(body.strip())
        return "\n\n".join(comments[:_MAX_COMMENTS])


def _post_date(post: dict) -> datetime.date | None:
    created = post.get("created_utc")
    if not created:
        return None
    return datetime.datetime.fromtimestamp(created, tz=datetime.timezone.utc).date()
