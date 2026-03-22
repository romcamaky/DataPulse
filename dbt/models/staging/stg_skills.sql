-- Staging layer for the canonical skills dimension. Passes through all columns from
-- public.skills for use in joins to user_skills and market_signals.
select
  id,
  name,
  display_name,
  parent_skill_id,
  category,
  created_at::timestamptz as created_at
from {{ source('datapulse', 'skills') }}
