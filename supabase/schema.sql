-- ============================================================
-- THE WORLD WITHIN — Supabase Database Schema
-- supabase/schema.sql
--
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- Run once. Safe to re-run (uses IF NOT EXISTS throughout).
-- ============================================================


-- ── Enable UUID extension (needed for auth.users) ─────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ============================================================
-- 1. USERS — profile + tier for every authenticated user
-- ============================================================
CREATE TABLE IF NOT EXISTS public.users (
  id           UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email        TEXT,
  name         TEXT,
  tier         TEXT        NOT NULL DEFAULT 'free'
                           CHECK (tier IN ('free','practitioner','premium','elite','owner')),
  platform     TEXT        NOT NULL DEFAULT ''
                           CHECK (platform IN ('','personal','bundle','enterprise','trial')),
  access_code  TEXT,                          -- hashed token stored here after validation
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS users_updated_at ON public.users;
CREATE TRIGGER users_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ============================================================
-- 2. SESSIONS — one row per user per day (the daily arc)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.sessions (
  id           BIGSERIAL   PRIMARY KEY,
  user_id      UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  session_date DATE        NOT NULL,
  data         JSONB       NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, session_date)
);

DROP TRIGGER IF EXISTS sessions_updated_at ON public.sessions;
CREATE TRIGGER sessions_updated_at
  BEFORE UPDATE ON public.sessions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX IF NOT EXISTS sessions_user_date ON public.sessions (user_id, session_date DESC);


-- ============================================================
-- 3. JOURNAL ENTRIES — morning, evening, and free entries
-- ============================================================
CREATE TABLE IF NOT EXISTS public.journal_entries (
  id           BIGSERIAL   PRIMARY KEY,
  user_id      UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  entry_id     TEXT        NOT NULL,          -- client-generated ID for dedup
  entry_type   TEXT,                          -- 'morning' | 'evening' | 'free'
  content      TEXT,
  iso_date     DATE,
  metadata     JSONB       NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, entry_id)
);

DROP TRIGGER IF EXISTS journal_entries_updated_at ON public.journal_entries;
CREATE TRIGGER journal_entries_updated_at
  BEFORE UPDATE ON public.journal_entries
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX IF NOT EXISTS journal_user_date ON public.journal_entries (user_id, iso_date DESC);


-- ============================================================
-- 4. USER SETTINGS — preferences, vision, identity config
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_settings (
  user_id      UUID        PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  settings     JSONB       NOT NULL DEFAULT '{}',
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS user_settings_updated_at ON public.user_settings;
CREATE TRIGGER user_settings_updated_at
  BEFORE UPDATE ON public.user_settings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ============================================================
-- 5. IDENTITY ENGINE — Future Identity, IOS profile data
-- ============================================================
CREATE TABLE IF NOT EXISTS public.identity_engine (
  user_id      UUID        PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  data         JSONB       NOT NULL DEFAULT '{}',
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS identity_engine_updated_at ON public.identity_engine;
CREATE TRIGGER identity_engine_updated_at
  BEFORE UPDATE ON public.identity_engine
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ============================================================
-- 6. PRACTICE SESSIONS — Fears, Silence, Synthesis sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS public.practice_sessions (
  id           BIGSERIAL   PRIMARY KEY,
  user_id      UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  session_type TEXT        NOT NULL,
  session_date DATE        NOT NULL DEFAULT CURRENT_DATE,
  data         JSONB       NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, session_type, session_date)
);

CREATE INDEX IF NOT EXISTS practice_user_type ON public.practice_sessions (user_id, session_type, session_date DESC);


-- ============================================================
-- 7. SUBSCRIBERS — Stripe subscription status (read by app)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.subscribers (
  id           BIGSERIAL   PRIMARY KEY,
  user_id      UUID        REFERENCES public.users(id) ON DELETE SET NULL,
  email        TEXT        NOT NULL,
  tier         TEXT        NOT NULL DEFAULT 'free',
  status       TEXT        NOT NULL DEFAULT 'active',  -- active | canceled | past_due
  stripe_id    TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS subscribers_updated_at ON public.subscribers;
CREATE TRIGGER subscribers_updated_at
  BEFORE UPDATE ON public.subscribers
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX IF NOT EXISTS subscribers_user ON public.subscribers (user_id);
CREATE INDEX IF NOT EXISTS subscribers_email ON public.subscribers (email);


-- ============================================================
-- 8. ENTERPRISE TABLES (World Within for Teams)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.enterprise_sessions (
  id            BIGSERIAL   PRIMARY KEY,
  user_id       UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  org_id        TEXT        NOT NULL,
  session_date  DATE        NOT NULL,
  data          JSONB       NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, session_date)
);

CREATE TABLE IF NOT EXISTS public.enterprise_team_intelligence (
  id             BIGSERIAL   PRIMARY KEY,
  org_id         TEXT        NOT NULL,
  generated_for  TEXT        NOT NULL,
  generated_date DATE        NOT NULL,
  data           JSONB       NOT NULL DEFAULT '{}',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (org_id, generated_for, generated_date)
);

CREATE TABLE IF NOT EXISTS public.enterprise_exec_reports (
  id           BIGSERIAL   PRIMARY KEY,
  user_id      UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  report_month TEXT        NOT NULL,   -- e.g. '2026-05'
  data         JSONB       NOT NULL DEFAULT '{}',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, report_month)
);


-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Users can only read and write their own rows.
-- Enterprise tables use org_id scoping.
-- ============================================================

ALTER TABLE public.users                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.journal_entries          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.identity_engine          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.practice_sessions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscribers              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enterprise_sessions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enterprise_team_intelligence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enterprise_exec_reports  ENABLE ROW LEVEL SECURITY;


-- users
DROP POLICY IF EXISTS "users: own row"    ON public.users;
CREATE POLICY "users: own row"    ON public.users
  FOR ALL USING (auth.uid() = id);

-- sessions
DROP POLICY IF EXISTS "sessions: own rows" ON public.sessions;
CREATE POLICY "sessions: own rows" ON public.sessions
  FOR ALL USING (auth.uid() = user_id);

-- journal_entries
DROP POLICY IF EXISTS "journal: own rows" ON public.journal_entries;
CREATE POLICY "journal: own rows" ON public.journal_entries
  FOR ALL USING (auth.uid() = user_id);

-- user_settings
DROP POLICY IF EXISTS "settings: own row" ON public.user_settings;
CREATE POLICY "settings: own row" ON public.user_settings
  FOR ALL USING (auth.uid() = user_id);

-- identity_engine
DROP POLICY IF EXISTS "identity: own row" ON public.identity_engine;
CREATE POLICY "identity: own row" ON public.identity_engine
  FOR ALL USING (auth.uid() = user_id);

-- practice_sessions
DROP POLICY IF EXISTS "practice: own rows" ON public.practice_sessions;
CREATE POLICY "practice: own rows" ON public.practice_sessions
  FOR ALL USING (auth.uid() = user_id);

-- subscribers (read-only for users; writes come from Stripe webhook)
DROP POLICY IF EXISTS "subscribers: read own" ON public.subscribers;
CREATE POLICY "subscribers: read own" ON public.subscribers
  FOR SELECT USING (auth.uid() = user_id);

-- enterprise_sessions
DROP POLICY IF EXISTS "ent_sessions: own rows" ON public.enterprise_sessions;
CREATE POLICY "ent_sessions: own rows" ON public.enterprise_sessions
  FOR ALL USING (auth.uid() = user_id);

-- enterprise_team_intelligence (org-scoped — users read their own org)
DROP POLICY IF EXISTS "ent_team: own org" ON public.enterprise_team_intelligence;
CREATE POLICY "ent_team: own org" ON public.enterprise_team_intelligence
  FOR SELECT USING (
    org_id IN (
      SELECT (data->>'org_id')::TEXT
      FROM public.enterprise_sessions
      WHERE user_id = auth.uid()
      LIMIT 1
    )
  );

-- enterprise_exec_reports
DROP POLICY IF EXISTS "ent_exec: own rows" ON public.enterprise_exec_reports;
CREATE POLICY "ent_exec: own rows" ON public.enterprise_exec_reports
  FOR ALL USING (auth.uid() = user_id);


-- ============================================================
-- AUTO-CREATE USER PROFILE ON SIGN-UP
-- Runs when a new user is created in auth.users
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.users (id, email, name, tier, platform)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_user_meta_data->>'tier', 'free'),
    COALESCE(NEW.raw_user_meta_data->>'platform', '')
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- ============================================================
-- Done. Tables, indexes, RLS policies, and auto-profile
-- trigger are all in place.
-- ============================================================
