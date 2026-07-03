"""Manually submit one story into the Story Scout AI Notion database.

Instagram, TikTok, and LinkedIn don't offer public content discovery the way
RSS/Reddit/YouTube do (see README's "Story Scout AI" section) -- there's no
legitimate automated source for them. This is the practical alternative: you
paste in a story you found by hand (its URL, platform, and whatever
caption/transcript/text is worth summarizing), and it runs through the same
brand/topic/summary/reaction/lesson/LinkedIn-angles generation as the
scheduled pipeline, landing in the same database. Comments/public reaction
are only included if you paste them in via --comments -- this script never
invents them.

Skips the LLM scoring step (you already decided it's worth including) and
skips it if the URL is already logged, same as the scheduled pipeline.

Usage:
    python -m src.story_scout.manual_entry \
        --url "https://www.instagram.com/p/abc123/" \
        --title "Silence, brand: the shift from funny to fatigued" \
        --source "Instagram (@girlsinmarketing)" \
        --platform "Instagram" \
        --text "Caption/transcript/description of the post, pasted in by hand." \
        --comments "Optional: paste real comment text here if you have it."
"""

import argparse
import datetime
import logging

from src.common import notion_client
from src.story_scout import notion_writer
from src.story_scout.config import load_config
from src.story_scout.llm import StoryScoutLLM
from src.story_scout.models import RawStory, ScoutedStory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("story_scout.manual_entry")


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="Link to the original post/article.")
    parser.add_argument("--title", required=True, help="Short title/headline for the story.")
    parser.add_argument("--source", required=True, help='Where it came from, e.g. "Instagram (@girlsinmarketing)".')
    parser.add_argument("--platform", required=True, help="e.g. Instagram, TikTok, LinkedIn, Reddit, YouTube, ...")
    parser.add_argument(
        "--text", required=True, help="Caption/transcript/description -- whatever text there is to summarize."
    )
    parser.add_argument(
        "--comments", default="", help="Optional: real comment text you observed, for the public-reaction field."
    )
    return parser.parse_args(argv)


def add_story(config, args: argparse.Namespace) -> None:
    notion = notion_client.NotionClient(config.notion_token, config.notion_story_database_id)

    if notion_writer.already_logged(notion, args.url):
        logger.info("Already logged in Notion, skipping: %s", args.url)
        return

    llm = StoryScoutLLM(api_key=config.anthropic_api_key, model=config.claude_model)
    raw = RawStory(
        source_name=args.source,
        platform=args.platform,
        title=args.title,
        url=args.url,
        published_at=datetime.date.today(),
        text=f"{args.title}\n\n{args.text}",
    )

    package = llm.generate_package(raw, comments_text=args.comments)
    notion.create_page(notion_writer.build_properties(ScoutedStory(raw=raw, package=package)))
    logger.info("Added to Notion: %s", args.title)


def main() -> None:
    add_story(load_config(), _parse_args())


if __name__ == "__main__":
    main()
