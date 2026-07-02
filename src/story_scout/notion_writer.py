"""Builds Notion page properties for a scouted story and checks for
already-logged URLs so daily runs don't re-add a story still circulating
within the lookback window.
"""

import datetime

from src.common import notion_client
from src.story_scout.models import ScoutedStory


def already_logged(notion: notion_client.NotionClient, url: str) -> bool:
    return notion.find_page_by_url("URL", url) is not None


def build_properties(story: ScoutedStory) -> dict:
    raw, package = story.raw, story.package
    return {
        "Name": notion_client.title_prop(raw.title),
        "URL": notion_client.url_prop(raw.url),
        "Source": notion_client.text_prop(raw.source_name),
        "Category": notion_client.select_prop(raw.category),
        "Published Date": notion_client.date_prop(raw.published_at.isoformat() if raw.published_at else None),
        "Date Added": notion_client.date_prop(datetime.date.today().isoformat()),
        "Summary": notion_client.text_prop(package.summary),
        "Why It Matters": notion_client.text_prop(package.why_it_matters),
        "LinkedIn Post Angle": notion_client.text_prop(package.linkedin_post_angle),
    }
