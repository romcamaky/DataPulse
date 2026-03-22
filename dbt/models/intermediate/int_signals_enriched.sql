/*
  int_signals_enriched
  Purpose: Enrich market signals with skill hierarchy and feed metadata for downstream demand and trend models.
  Source models: stg_market_signals, stg_skills, stg_feed_items
*/

with signals as (
  select * from {{ ref('stg_market_signals') }}
)

select
  ms.id as signal_id,
  ms.feed_item_id,
  ms.skill_id,
  coalesce(sk.display_name, ms.skill_name_raw) as skill_display_name,
  ms.skill_name_raw,
  case
    when sk.id is not null then sk.category
    else 'unmapped'
  end as skill_category,
  parent.display_name as parent_skill_name,
  ms.signal_type,
  ms.strength,
  ms.confidence,
  ms.region,
  ms.summary,
  fi.source_category,
  fi.published_at,
  fi.language,
  current_date - fi.published_at::date as signal_age_days,
  ms.has_canonical_skill
from signals as ms
left join {{ ref('stg_skills') }} as sk
  on ms.skill_id = sk.id
left join {{ ref('stg_skills') }} as parent
  on sk.parent_skill_id = parent.id
left join {{ ref('stg_feed_items') }} as fi
  on ms.feed_item_id = fi.id
