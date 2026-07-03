"""Builds Notion page properties for a scouted story and checks for
already-logged URLs so repeat runs don't re-add a story still circulating.
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
        "Brand": notion_client.text_prop(package.brand),
        "Platform": notion_client.select_prop(raw.platform),
        "Topic": notion_client.select_prop(package.topic),
        "URL": notion_client.url_prop(raw.url),
        "Source": notion_client.text_prop(raw.source_name),
        "Published Date": notion_client.date_prop(raw.published_at.isoformat() if raw.published_at else None),
        "Date Added": notion_client.date_prop(datetime.date.today().isoformat()),
        "Score": notion_client.number_prop(package.score),
        "Summary": notion_client.text_prop(package.summary),
        "Why It Matters": notion_client.text_prop(package.why_it_matters),
        "Public Reaction": notion_client.text_prop(package.public_reaction),
        "Marketing Lesson": notion_client.text_prop(package.marketing_lesson),
        "LinkedIn Post Angles": notion_client.text_prop(_format_post_angles(package.linkedin_post_angles)),
    }


def _format_post_angles(angles: list[str]) -> str:
    return "\n".join(f"{i + 1}. {angle}" for i, angle in enumerate(angles))
