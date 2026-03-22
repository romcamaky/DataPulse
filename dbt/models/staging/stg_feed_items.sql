-- Staging layer for raw RSS feed articles. Includes days_since_published for recency
-- filtering without repeating date math in every downstream model.
select
  id,
  source_key,
  source_category,
  url,
  title,
  summary,
  author,
  published_at::timestamptz as published_at,
  fetched_at::timestamptz as fetched_at,
  language,
  is_processed,
  current_date - published_at::date as days_since_published
from {{ source('datapulse', 'feed_items') }}
