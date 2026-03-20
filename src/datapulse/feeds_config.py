"""
Configured RSS sources for DataPulse market intelligence ingestion.

Each dict describes one feed: database ``source_key`` / ``source_category``,
HTTP ``url``, default ``language``, and ``region`` for future ``market_signals``
enrichment (not stored on ``feed_items`` today).
"""

from __future__ import annotations

from typing import TypedDict


class FeedConfig(TypedDict):
    """Single RSS source definition used by the collector."""

    key: str
    name: str
    url: str
    category: str
    language: str
    region: str


# Module 2 RSS sources (31 feeds: 30 typical + dormant asociace_ai). Order follows
# the product spec (vendor → ai_research → …) so logs remain easy to scan.
FEEDS: list[FeedConfig] = [
    # --- vendor (6) ---
    {
        "key": "databricks_blog",
        "name": "Databricks Blog",
        "url": "https://databricks.com/feed",
        "category": "vendor",
        "language": "en",
        "region": "global",
    },
    {
        "key": "dbt_labs_blog",
        "name": "dbt Labs Blog",
        "url": "https://www.getdbt.com/blog/rss.xml",
        "category": "vendor",
        "language": "en",
        "region": "global",
    },
    {
        "key": "snowflake_blog",
        "name": "Snowflake Blog",
        "url": "https://www.snowflake.com/feed/",
        "category": "vendor",
        "language": "en",
        "region": "global",
    },
    {
        "key": "supabase_blog",
        "name": "Supabase Blog",
        "url": "https://supabase.com/blog/rss.xml",
        "category": "vendor",
        "language": "en",
        "region": "global",
    },
    {
        "key": "google_cloud_blog",
        "name": "Google Cloud Blog",
        "url": "https://cloudblog.withgoogle.com/rss/",
        "category": "vendor",
        "language": "en",
        "region": "global",
    },
    {
        "key": "aws_big_data_blog",
        "name": "AWS Big Data Blog",
        "url": "https://aws.amazon.com/blogs/big-data/feed/",
        "category": "vendor",
        "language": "en",
        "region": "global",
    },
    # --- ai_research (6) ---
    {
        "key": "anthropic_news",
        "name": "Anthropic News",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
        "category": "ai_research",
        "language": "en",
        "region": "global",
    },
    {
        "key": "anthropic_engineering",
        "name": "Anthropic Engineering",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
        "category": "ai_research",
        "language": "en",
        "region": "global",
    },
    {
        "key": "openai_blog",
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "category": "ai_research",
        "language": "en",
        "region": "global",
    },
    {
        "key": "deepmind_blog",
        "name": "DeepMind Blog",
        "url": "https://deepmind.google/blog/rss.xml",
        "category": "ai_research",
        "language": "en",
        "region": "global",
    },
    {
        "key": "google_research_blog",
        "name": "Google Research Blog",
        "url": "https://research.google/blog/rss",
        "category": "ai_research",
        "language": "en",
        "region": "global",
    },
    {
        "key": "cursor_blog",
        "name": "Cursor Blog",
        "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_cursor.xml",
        "category": "ai_research",
        "language": "en",
        "region": "global",
    },
    # --- community (6) ---
    {
        "key": "hacker_news_best",
        "name": "Hacker News (best)",
        "url": "https://hnrss.org/best",
        "category": "community",
        "language": "en",
        "region": "global",
    },
    {
        "key": "data_engineering_weekly",
        "name": "Data Engineering Weekly",
        "url": "https://www.dataengineeringweekly.com/feed",
        "category": "community",
        "language": "en",
        "region": "global",
    },
    {
        "key": "towards_data_science",
        "name": "Towards Data Science",
        "url": "https://towardsdatascience.com/feed",
        "category": "community",
        "language": "en",
        "region": "global",
    },
    {
        "key": "data_engineer_things",
        "name": "Data Engineer Things",
        "url": "https://blog.dataengineerthings.org/feed",
        "category": "community",
        "language": "en",
        "region": "global",
    },
    {
        "key": "reddit_dataengineering",
        "name": "r/dataengineering",
        "url": "https://www.reddit.com/r/dataengineering/.rss",
        "category": "community",
        "language": "en",
        "region": "global",
    },
    {
        "key": "reddit_analytics",
        "name": "r/analytics",
        "url": "https://www.reddit.com/r/analytics/.rss",
        "category": "community",
        "language": "en",
        "region": "global",
    },
    # --- industry (3) ---
    {
        "key": "pragmatic_engineer",
        "name": "Pragmatic Engineer",
        "url": "https://newsletter.pragmaticengineer.com/feed",
        "category": "industry",
        "language": "en",
        "region": "global",
    },
    {
        "key": "datanami",
        "name": "Datanami",
        "url": "https://www.datanami.com/feed/",
        "category": "industry",
        "language": "en",
        "region": "global",
    },
    {
        "key": "kdnuggets",
        "name": "KDnuggets",
        "url": "https://www.kdnuggets.com/feed",
        "category": "industry",
        "language": "en",
        "region": "global",
    },
    # --- practitioner (2) ---
    {
        "key": "seattle_data_guy",
        "name": "Seattle Data Guy",
        "url": "https://www.theseattledataguy.com/feed",
        "category": "practitioner",
        "language": "en",
        "region": "global",
    },
    {
        "key": "locally_optimistic",
        "name": "Locally Optimistic",
        "url": "https://locallyoptimistic.com/feed/",
        "category": "practitioner",
        "language": "en",
        "region": "global",
    },
    # --- eu_regulation (4) ---
    {
        "key": "eu_ai_act_newsletter",
        "name": "EU AI Act Newsletter",
        "url": "https://artificialintelligenceact.substack.com/feed",
        "category": "eu_regulation",
        "language": "en",
        "region": "eu",
    },
    {
        "key": "ec_digital_strategy",
        "name": "EC Digital Strategy",
        "url": "https://digital-strategy.ec.europa.eu/en/rss.xml",
        "category": "eu_regulation",
        "language": "en",
        "region": "eu",
    },
    {
        "key": "the_gradient",
        "name": "The Gradient",
        "url": "https://thegradient.pub/rss/",
        "category": "eu_regulation",
        "language": "en",
        "region": "global",
    },
    {
        "key": "microsoft_eu_blog",
        "name": "Microsoft EU Policy Blog",
        "url": "https://blogs.microsoft.com/eupolicy/feed/",
        "category": "eu_regulation",
        "language": "en",
        "region": "eu",
    },
    # --- czech_cee (4) ---
    {
        "key": "lupa_cz",
        "name": "Lupa.cz",
        "url": "https://www.lupa.cz/rss/clanky/",
        "category": "czech_cee",
        "language": "cs",
        "region": "cz",
    },
    {
        "key": "root_cz",
        "name": "Root.cz",
        "url": "https://www.root.cz/rss/clanky/",
        "category": "czech_cee",
        "language": "cs",
        "region": "cz",
    },
    {
        "key": "czechcrunch",
        "name": "CzechCrunch",
        "url": "https://czechcrunch.cz/feed/",
        "category": "czech_cee",
        "language": "cs",
        "region": "cz",
    },
    {
        "key": "asociace_ai",
        "name": "Asociace AI",
        "url": "https://asociace.ai/zpravy/",
        "category": "czech_cee",
        "language": "cs",
        "region": "cz",
    },
]
