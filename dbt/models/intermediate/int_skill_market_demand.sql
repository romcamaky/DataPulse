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
    ) as raw_demand_score,
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
),

normalized as (
  select
    *,
    max(raw_demand_score) over () as max_demand_score,
    round(
      raw_demand_score / nullif(max(raw_demand_score) over (), 0) * 10,
      2
    ) as demand_score
  from aggregated
)

select
  n.skill_id,
  n.skill_display_name,
  n.skill_category,
  n.parent_skill_name,
  n.signal_count,
  n.avg_strength,
  n.avg_confidence,
  n.raw_demand_score,
  n.demand_score,
  n.latest_signal_date,
  coalesce(tb.signal_type_breakdown, '{}'::jsonb) as signal_type_breakdown,
  n.regions,
  n.source_categories
from normalized as n
left join type_breakdown as tb
  on n.skill_id = tb.skill_id
order by n.demand_score desc
