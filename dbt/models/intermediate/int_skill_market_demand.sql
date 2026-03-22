/*
  int_skill_market_demand
  Purpose: Aggregate market signals into a demand score per canonical skill (market appetite).
  Source models: int_signals_enriched
*/

with filtered as (
  select *
  from {{ ref('int_signals_enriched') }}
  where has_canonical_skill
),

signal_type_counts as (
  select
    skill_id,
    signal_type,
    count(*)::bigint as type_cnt
  from filtered
  group by skill_id, signal_type
),

type_breakdown as (
  select
    skill_id,
    jsonb_object_agg(signal_type::text, type_cnt) as signal_type_breakdown
  from signal_type_counts
  group by skill_id
),

aggregated as (
  select
    skill_id,
    max(skill_display_name) as skill_display_name,
    max(skill_category) as skill_category,
    max(parent_skill_name) as parent_skill_name,
    count(*)::bigint as signal_count,
    round(avg(strength)::numeric, 2) as avg_strength,
    round(avg(confidence)::numeric, 2) as avg_confidence,
    -- Weight strong signals more than weak ones, then scale by log frequency so rare noise does not dominate.
    round(
      (avg(strength)::numeric * 0.6 + avg(confidence)::numeric * 0.4)
      * ln(count(*)::numeric + 1.0),
      2
    ) as demand_score,
    max(published_at::date) as latest_signal_date,
    coalesce(
      array_agg(distinct region) filter (where region is not null),
      array[]::text[]
    ) as regions,
    coalesce(
      array_agg(distinct source_category) filter (where source_category is not null),
      array[]::text[]
    ) as source_categories
  from filtered
  group by skill_id
)

select
  a.skill_id,
  a.skill_display_name,
  a.skill_category,
  a.parent_skill_name,
  a.signal_count,
  a.avg_strength,
  a.avg_confidence,
  a.demand_score,
  a.latest_signal_date,
  coalesce(tb.signal_type_breakdown, '{}'::jsonb) as signal_type_breakdown,
  a.regions,
  a.source_categories
from aggregated as a
left join type_breakdown as tb
  on a.skill_id = tb.skill_id
order by a.demand_score desc
