-- Staging layer for user profile attributes used in analytics and Module 3+ modeling.
-- We subset columns here: identity and professional context only. JSONB blobs (languages,
-- platform_access, ai_tools, etc.) and optional social/thesis fields are deferred to
-- Module 5 enrichment models.
select
  id,
  user_id,
  display_name,
  role_title,
  industry,
  country,
  years_total_experience,
  years_in_current_role,
  weekly_hours_available,
  learning_preferences,
  career_narrative,
  ai_usage_frequency,
  ai_api_experience,
  ai_automation_level,
  created_at::timestamptz as created_at,
  updated_at::timestamptz as updated_at
from {{ source('datapulse', 'user_profiles') }}
