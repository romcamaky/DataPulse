-- Staging layer for roles users are targeting. Passes through all columns from
-- public.user_target_roles for downstream career and market alignment models.
select
  id,
  user_id,
  role_name,
  priority,
  created_at::timestamptz as created_at,
  timeline,
  market_scope
from {{ source('datapulse', 'user_target_roles') }}
