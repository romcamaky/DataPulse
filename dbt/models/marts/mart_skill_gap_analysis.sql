/*
  mart_skill_gap_analysis
  Purpose: Ranked skill gaps per user for recommendations and reporting (materialized for Python consumers).
  Source models: int_user_skill_coverage
*/

with ranked as (
  select
    *,
    row_number() over (
      partition by user_id
      order by gap_score desc
    ) as gap_rank
  from {{ ref('int_user_skill_coverage') }}
  where gap_score > 0
)

select
  user_id,
  skill_id,
  skill_display_name,
  skill_category,
  parent_skill_name,
  user_level,
  evidence_type,
  demand_score,
  signal_count,
  gap_score,
  gap_rank,
  gap_category,
  case
    when gap_rank <= 5 then 'critical'
    when gap_rank <= 15 then 'important'
    else 'nice_to_have'
  end as priority_tier
from ranked
