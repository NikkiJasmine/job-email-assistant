"""Curated list of trusted RSS feeds Story Scout searches for stories.

Edit this list to add/remove sources -- no other code needs to change. Each
entry is (display_name, category, feed_url). Categories are written as-is
into the Notion database's Category property, so keep them short and
consistent across feeds.

Feed URLs occasionally change or get restructured by the publisher; if a
feed starts returning zero stories, check the outlet's site for its current
RSS link and update the entry here.
"""

TRUSTED_RSS_FEEDS = [
    ("HubSpot Marketing Blog", "Marketing", "https://blog.hubspot.com/marketing/rss.xml"),
    ("Marketing Dive", "Marketing", "https://www.marketingdive.com/feeds/news/"),
    ("Search Engine Land", "Marketing", "https://searchengineland.com/feed"),
    ("TechCrunch AI", "AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI", "AI", "https://venturebeat.com/category/ai/feed/"),
    ("Fast Company: Co.Design", "Branding", "https://www.fastcompany.com/co-design/rss"),
    ("Fast Company: Work Life", "Branding", "https://www.fastcompany.com/work-life/rss"),
    ("ICYMI (Lia Haberman)", "Creator Economy", "https://liahaberman.substack.com/feed"),
    ("Mike Shields", "Creator Economy", "https://mikeshields.substack.com/feed"),
    ("Adweek", "Advertising", "https://www.adweek.com/feed/"),
    ("Digiday", "Advertising", "https://digiday.com/feed/"),
    ("PRWeek", "PR", "https://www.prweek.com/us/rss"),
    ("Social Media Today", "Social Media", "https://www.socialmediatoday.com/feeds/news/"),
    ("Harvard Business Review", "Consumer Behavior", "http://feeds.harvardbusiness.org/harvardbusiness"),
]
