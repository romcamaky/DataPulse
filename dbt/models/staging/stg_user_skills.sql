-- Staging layer for user self-assessed skills. Passes through all columns from
-- public.user_skills for downstream fact and bridge models.
select
  id,
  user_id,
  skill_id,
  level,
  confidence,
  evidence_type,
  evidence_detail,
  visibility,
  last_assessed_at::timestamptz as last_assessed_at,
  created_at::timestamptz as created_at,
  updated_at::timestamptz as updated_at
from {{ source('datapulse', 'user_skills') }}
