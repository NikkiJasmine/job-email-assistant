"""Daily pipeline: RSS feeds -> dedup -> relevance filter -> generate -> Notion -> notify."""

import datetime
import logging

from src.common import gmail_client, notion_client
from src.story_scout import dedup, notifier, notion_writer
from src.story_scout.config import load_config
from src.story_scout.llm import StoryScoutLLM
from src.story_scout.models import ScoutedStory
from src.story_scout.sources import get_enabled_sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("story_scout")


def run() -> None:
    config = load_config()
    notion = notion_client.NotionClient(config.notion_token, config.notion_story_database_id)
    llm = StoryScoutLLM(api_key=config.anthropic_api_key, model=config.claude_model)

    since = datetime.date.today() - datetime.timedelta(days=config.lookback_days)

    raw_stories = []
    for source in get_enabled_sources():
        try:
            fetched = source.fetch_recent(since)
            logger.info("Fetched %d stor(y/ies) from %s", len(fetched), source.name)
            raw_stories.extend(fetched)
        except Exception:
            logger.exception("Failed fetching from %s; skipping this source", source.name)

    deduped = dedup.remove_duplicates(raw_stories)
    logger.info("%d candidate(s) after dedup (from %d fetched)", len(deduped), len(raw_stories))

    new_candidates = [story for story in deduped if not notion_writer.already_logged(notion, story.url)]
    logger.info("%d candidate(s) not already logged in Notion", len(new_candidates))

    relevant = llm.filter_relevant(new_candidates)
    logger.info("%d stor(y/ies) judged relevant for the LinkedIn audience", len(relevant))

    failure_count = 0
    written_stories = []
    for raw in relevant:
        try:
            package = llm.generate_package(raw)
            scouted = ScoutedStory(raw=raw, package=package)
            notion.create_page(notion_writer.build_properties(scouted))
            written_stories.append(scouted)
        except Exception:
            failure_count += 1
            logger.exception("Failed generating/writing story %r; will retry next run", raw.url)

    logger.info("Run complete: %d story(ies) written, %d failed", len(written_stories), failure_count)

    try:
        gmail = gmail_client.build_service(
            config.google_client_id, config.google_client_secret, config.google_refresh_token
        )
        notifier.send_digest_email(gmail, config.notify_email, written_stories)
    except Exception:
        # Notion is already up to date at this point -- a notification failure
        # shouldn't be treated as a run failure, just logged.
        logger.exception("Failed sending digest email; stories are still saved in Notion")

    # If every relevant story failed to save, that's very unlikely to be a
    # batch of unrelated per-story flukes -- it's much more likely a systemic
    # problem (bad credentials, wrong Notion database id, etc). Fail loudly so
    # GitHub Actions reports the run as failed.
    if relevant and failure_count == len(relevant):
        raise RuntimeError(
            f"All {failure_count} relevant stor(y/ies) failed to process -- "
            "likely a systemic issue (credentials, Notion database id, etc), "
            "not per-story flukes. See exception logs above for the root cause."
        )


if __name__ == "__main__":
    run()
