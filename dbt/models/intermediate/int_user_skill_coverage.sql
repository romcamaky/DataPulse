/*
  int_user_skill_coverage
  Purpose: Cross every user with every in-demand skill and measure level vs market demand (gap detection input).
  Source models: int_skill_market_demand, stg_user_profiles, stg_user_skills
*/

with users as (
  select distinct user_id
  from {{ ref('stg_user_profiles') }}
),

demand as (
  select * from {{ ref('int_skill_market_demand') }}
),

user_skill_grid as (
  select
    u.user_id,
    d.skill_id,
    d.skill_display_name,
    d.skill_category,
    d.parent_skill_name,
    coalesce(us.level, 0) as user_level,
    us.evidence_type,
    d.demand_score,
    d.signal_count,
    -- High market demand matters most when the user is weak; level 5 forces gap_score to zero.
    round(d.demand_score * (5 - coalesce(us.level, 0)) / 5.0, 2) as gap_score,
    case
      when coalesce(us.level, 0) = 0 then 'missing'
      when coalesce(us.level, 0) <= 2 then 'weak'
      when coalesce(us.level, 0) <= 3 then 'developing'
      when coalesce(us.level, 0) >= 4 then 'strong'
    end as gap_category
  from users as u
  cross join demand as d
  left join {{ ref('stg_user_skills') }} as us
    on us.user_id = u.user_id
    and us.skill_id = d.skill_id
)

select * from user_skill_grid
