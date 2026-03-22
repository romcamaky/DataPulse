/*
  mart_trend_summary
  Purpose: Top trending skills in the last 90 days for weekly report headers.
  Source models: int_signals_enriched
*/

with filtered as (
  select *
  from {{ ref('int_signals_enriched') }}
  where signal_age_days <= 90
),

type_counts as (
  select
    skill_display_name,
    skill_category,
    has_canonical_skill,
    signal_type,
    count(*)::bigint as type_cnt
  from filtered
  group by skill_display_name, skill_category, has_canonical_skill, signal_type
),

ranked_types as (
  select
    skill_display_name,
    skill_category,
    has_canonical_skill,
    signal_type,
    row_number() over (
      partition by skill_display_name, skill_category, has_canonical_skill
      order by type_cnt desc, signal_type
    ) as rn
  from type_counts
),

dominant as (
  select
    skill_display_name,
    skill_category,
    has_canonical_skill,
    signal_type as dominant_signal_type
  from ranked_types
  where rn = 1
),

aggregated as (
  select
    f.skill_display_name,
    f.skill_category,
    f.has_canonical_skill,
    count(*)::bigint as signal_count,
    round(avg(f.strength)::numeric, 2) as avg_strength,
    coalesce(
      array_agg(distinct f.region) filter (where f.region is not null),
      array[]::text[]
    ) as regions,
    round(
      count(*)::numeric * avg(f.strength)::numeric * avg(f.confidence)::numeric / 10.0,
      2
    ) as trending_score
  from filtered as f
  group by f.skill_display_name, f.skill_category, f.has_canonical_skill
)

select
  a.skill_display_name,
  a.skill_category,
  a.has_canonical_skill,
  a.signal_count,
  a.avg_strength,
  d.dominant_signal_type,
  a.regions,
  a.trending_score
from aggregated as a
join dominant as d
  on a.skill_display_name = d.skill_display_name
  and a.skill_category = d.skill_category
  and a.has_canonical_skill = d.has_canonical_skill
where a.signal_count >= 2
order by a.trending_score desc
limit 30
