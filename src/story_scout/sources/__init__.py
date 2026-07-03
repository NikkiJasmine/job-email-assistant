"""Assembles the list of enabled discovery sources for a Story Scout run.

RSS is always enabled. Reddit and YouTube activate automatically once their
credentials are set (see config.py) and are skipped with a log message
otherwise, so the pipeline keeps working on RSS alone until you add them.

Instagram, TikTok, and LinkedIn have no legitimate public content-discovery
API -- scraping them means fighting active bot detection and breaching
their Terms of Service, so they are deliberately not implemented here. See
src/story_scout/manual_entry.py for feeding in stories from those platforms
by hand.
"""

import logging

from src.story_scout.sources.base import Source
from src.story_scout.sources.feeds import TRUSTED_RSS_FEEDS
from src.story_scout.sources.reddit import RedditSource
from src.story_scout.sources.rss import RSSSource
from src.story_scout.sources.youtube import YouTubeSource

logger = logging.getLogger("story_scout.sources")


def get_enabled_sources(config) -> list[Source]:
    sources: list[Source] = [RSSSource(name, url) for name, url in TRUSTED_RSS_FEEDS]

    if config.reddit_client_id and config.reddit_client_secret:
        sources.append(RedditSource(config.reddit_client_id, config.reddit_client_secret))
    else:
        logger.info("REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET not set -- skipping Reddit")

    if config.youtube_api_key:
        sources.append(YouTubeSource(config.youtube_api_key))
    else:
        logger.info("YOUTUBE_API_KEY not set -- skipping YouTube")

    return sources
