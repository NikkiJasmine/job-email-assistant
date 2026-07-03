"""Curated list of trusted RSS feeds Story Scout searches for stories.

Edit this list to add/remove sources -- no other code needs to change. Each
entry is (display_name, feed_url). The LLM classifies each story's topic and
brand itself (see llm.py), so no per-feed category tagging is needed here.

Feed URLs occasionally change or get restructured by the publisher; if a
feed starts returning zero stories, check the outlet's site for its current
RSS link and update the entry here.
"""

TRUSTED_RSS_FEEDS = [
    # Marketing trade press
    ("HubSpot Marketing Blog", "https://blog.hubspot.com/marketing/rss.xml"),
    ("Marketing Dive", "https://www.marketingdive.com/feeds/news/"),
    ("Search Engine Land", "https://searchengineland.com/feed"),
    ("Content Marketing Institute", "https://contentmarketinginstitute.com/feed/"),
    # AI
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    # Branding / creative
    ("Fast Company: Co.Design", "https://www.fastcompany.com/co-design/rss"),
    ("Fast Company: Work Life", "https://www.fastcompany.com/work-life/rss"),
    # Creator economy
    ("ICYMI (Lia Haberman)", "https://liahaberman.substack.com/feed"),
    ("Mike Shields", "https://mikeshields.substack.com/feed"),
    # Advertising
    ("Adweek", "https://www.adweek.com/feed/"),
    ("Digiday", "https://digiday.com/feed/"),
    # PR
    ("PRWeek", "https://www.prweek.com/us/rss"),
    # Social media
    ("Social Media Today", "https://www.socialmediatoday.com/feeds/news/"),
    # Consumer behavior / business
    ("Harvard Business Review", "http://feeds.harvardbusiness.org/harvardbusiness"),
    # Brand newsrooms / company blogs
    ("Apple Newsroom", "https://www.apple.com/newsroom/rss-feed.rss"),
    ("Google Blog", "https://blog.google/feed/"),
]
