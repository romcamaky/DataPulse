{#
  Re-apply RLS after each dbt rebuild: per-user SELECT for authenticated;
  writes denied (service role bypasses RLS for pipeline jobs).
#}
{{
  config(
    post_hook=[
      "ALTER TABLE {{ this }} ENABLE ROW LEVEL SECURITY",
      "DROP POLICY IF EXISTS mart_skill_gap_select_own ON {{ this }}",
      "CREATE POLICY mart_skill_gap_select_own ON {{ this }} FOR SELECT TO authenticated USING (auth.uid() = user_id)",
      "DROP POLICY IF EXISTS mart_skill_gap_insert_deny ON {{ this }}",
      "CREATE POLICY mart_skill_gap_insert_deny ON {{ this }} FOR INSERT TO authenticated WITH CHECK (false)",
      "DROP POLICY IF EXISTS mart_skill_gap_update_deny ON {{ this }}",
      "CREATE POLICY mart_skill_gap_update_deny ON {{ this }} FOR UPDATE TO authenticated USING (false)",
      "DROP POLICY IF EXISTS mart_skill_gap_delete_deny ON {{ this }}",
      "CREATE POLICY mart_skill_gap_delete_deny ON {{ this }} FOR DELETE TO authenticated USING (false)",
    ],
  )
}}

/*
  mart_skill_gap_analysis
  Purpose: Ranked skill gaps per user for recommendations and reporting (materialized for Python consumers).
  Source models: int_user_skill_coverage
*/

with ranked as (
  select
    *,
    max(gap_score) over (partition by user_id) as max_gap_score,
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
  round(
    gap_score / nullif(max_gap_score, 0) * 10,
    2
  ) as gap_score_normalized,
  gap_rank,
  gap_category,
  case
    when gap_rank <= 5 then 'critical'
    when gap_rank <= 15 then 'important'
    else 'nice_to_have'
  end as priority_tier
from ranked
