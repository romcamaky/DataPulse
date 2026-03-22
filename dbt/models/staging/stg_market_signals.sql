-- Staging layer for Claude-extracted market intelligence linked to feed items and skills.
-- has_canonical_skill flags rows mapped to the skills dimension for simpler downstream filters.
select
  id,
  feed_item_id,
  skill_id,
  skill_name_raw,
  signal_type,
  strength,
  confidence,
  region,
  summary,
  extracted_at::timestamptz as extracted_at,
  skill_id is not null as has_canonical_skill
from {{ source('datapulse', 'market_signals') }}
