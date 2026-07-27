-- Migration: Embed API key management & full backend storage for the
-- embed widget feature.
--
-- Replaces the previous flat-file `embed-configs.json` store with proper
-- Postgres tables: `embed_configs`, `api_keys`, `embed_feedback`.
--
-- Run this against the same Postgres instance used by the chat service
-- (see app/core/config.py -> DATABASE_HOST/DATABASE_NAME/...).
--
-- Safe to re-run: uses IF NOT EXISTS / CREATE OR REPLACE where possible.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ──────────────────────────────────────────────
-- embed_configs
-- ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS embed_configs (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               TEXT NOT NULL,               -- Cognito sub / userId

    -- Identity
    bot_name              TEXT NOT NULL,
    bot_description       TEXT,

    -- Messages
    welcome_message       TEXT NOT NULL,
    fallback_message      TEXT NOT NULL,
    suggested_questions   TEXT[] NOT NULL DEFAULT '{}',

    -- Branding
    primary_color         TEXT NOT NULL DEFAULT '#0f172a',
    chat_background       TEXT,
    position              TEXT NOT NULL DEFAULT 'bottom-right',
    launcher_label        TEXT NOT NULL DEFAULT 'Chat',
    launcher_style        TEXT DEFAULT 'circle',       -- 'circle'|'rounded'|'square'
    avatar_initials       TEXT NOT NULL,
    border_radius_style   TEXT DEFAULT 'rounded',
    widget_shadow         TEXT DEFAULT 'soft',
    font_family           TEXT DEFAULT 'system',
    show_powered_by       BOOLEAN DEFAULT TRUE,

    -- Security & settings
    allowed_origins       TEXT[] NOT NULL DEFAULT '{}',
    collect_visitor_email BOOLEAN DEFAULT FALSE,
    is_active             BOOLEAN DEFAULT TRUE,
    model                 TEXT,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS embed_configs_user_id_idx ON embed_configs(user_id);

-- ──────────────────────────────────────────────
-- api_keys
-- ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS api_keys (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id     UUID NOT NULL REFERENCES embed_configs(id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL,

    key_hash      TEXT NOT NULL UNIQUE,    -- SHA-256(rawKey), hex-encoded
    key_prefix    TEXT NOT NULL,           -- first 12 chars shown in UI e.g. "dk_live_a1b2"
    name          TEXT DEFAULT 'Default',

    is_active     BOOLEAN DEFAULT TRUE,
    last_used_at  TIMESTAMPTZ,
    expires_at    TIMESTAMPTZ,             -- NULL = never expires
    revoked_at    TIMESTAMPTZ,             -- NULL = active

    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_keys_config_id_idx ON api_keys(config_id);
CREATE INDEX IF NOT EXISTS api_keys_key_hash_idx  ON api_keys(key_hash);

-- ──────────────────────────────────────────────
-- embed_feedback
-- ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS embed_feedback (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id     UUID NOT NULL REFERENCES embed_configs(id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL,

    thread_id     TEXT,
    question      TEXT NOT NULL,
    answer        TEXT,
    visitor_email TEXT,
    page_url      TEXT,
    parent_origin TEXT,
    reason        TEXT NOT NULL
        CHECK (reason IN ('not_helpful', 'needs_human', 'gap_detected')),

    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS embed_feedback_config_id_idx ON embed_feedback(config_id);
CREATE INDEX IF NOT EXISTS embed_feedback_user_id_idx   ON embed_feedback(user_id);
