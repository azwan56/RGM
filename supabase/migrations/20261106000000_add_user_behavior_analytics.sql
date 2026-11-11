-- ============================================================================
-- Migration: Add MiniApp User Behavior Sessions & Event Stream Tables
-- Purpose: Captures per-user session lifecycle, page stay duration, scroll depth,
--          button clicks, modal interactions, and funnel steps from open to exit.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.miniapp_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    client_uuid TEXT,
    scene INTEGER,
    scene_label TEXT,
    entry_page TEXT,
    exit_page TEXT,
    inviter_uid TEXT,
    device_model TEXT,
    platform TEXT,
    app_version TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_event_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_ms BIGINT DEFAULT 0,
    page_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    max_scroll_pct INTEGER DEFAULT 0,
    had_error BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_miniapp_sessions_started ON public.miniapp_sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_miniapp_sessions_user ON public.miniapp_sessions(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_miniapp_sessions_client ON public.miniapp_sessions(client_uuid, started_at DESC);

CREATE TABLE IF NOT EXISTS public.miniapp_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    event_id TEXT,
    user_id TEXT,
    client_uuid TEXT,
    event_type TEXT NOT NULL,
    event_name TEXT NOT NULL,
    event_label TEXT,
    page_path TEXT,
    page_title TEXT,
    stay_ms BIGINT DEFAULT 0,
    scroll_pct INTEGER DEFAULT NULL,
    props_json JSONB,
    client_ts BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_miniapp_events_dedup
    ON public.miniapp_events(session_id, event_id) WHERE event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_miniapp_events_session ON public.miniapp_events(session_id, client_ts ASC, id ASC);
CREATE INDEX IF NOT EXISTS idx_miniapp_events_user ON public.miniapp_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_miniapp_events_type ON public.miniapp_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_miniapp_events_page ON public.miniapp_events(page_path, created_at DESC);
