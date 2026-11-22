-- Migration: Add Official Pacer Evaluation & Credentials Support
-- Date: 2026-11-04

ALTER TABLE IF EXISTS profiles
  ADD COLUMN IF NOT EXISTS first_aid_cert_type TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS pacer_bio_tags TEXT DEFAULT '';

ALTER TABLE IF EXISTS race_plans
  ADD COLUMN IF NOT EXISTS was_official_pacer BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS pacer_target_time TEXT DEFAULT '';

CREATE TABLE IF NOT EXISTS race_intel_cache (
  cache_key TEXT PRIMARY KEY,
  event_name TEXT NOT NULL,
  race_category TEXT DEFAULT 'road',
  race_info_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  source TEXT DEFAULT 'official_web_search',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE IF EXISTS public.race_intel_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read race_intel_cache"
  ON public.race_intel_cache FOR SELECT
  TO authenticated
  USING (true);
