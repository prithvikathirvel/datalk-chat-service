-- Migration: conversation analytics write-time aggregation.
--
-- Stores near-duplicate user questions in a small aggregate table using
-- pg_trgm, so analytics can fetch top questions without grouping/scanning the
-- large conversation table on every request.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE conversation
ADD COLUMN IF NOT EXISTS rewritten_query TEXT;

ALTER TABLE conversation
ADD COLUMN IF NOT EXISTS final_node TEXT;

CREATE TABLE IF NOT EXISTS conversation_question_stats (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  TEXT NOT NULL,
    chatbot_id               UUID,
    chatbot_name             TEXT,
    question                 TEXT NOT NULL,
    normalized_question      TEXT NOT NULL,
    count                    INTEGER NOT NULL DEFAULT 1,
    unanswered_count         INTEGER NOT NULL DEFAULT 0,
    first_conversation_id    UUID,
    last_conversation_id     UUID,
    first_asked              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_asked               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS conversation_question_stats_user_bot_count_idx
ON conversation_question_stats(user_id, chatbot_id, count DESC, last_asked DESC);

CREATE INDEX IF NOT EXISTS conversation_question_stats_normalized_trgm_idx
ON conversation_question_stats USING GIN (normalized_question gin_trgm_ops);

CREATE INDEX IF NOT EXISTS conversation_user_chatbot_created_idx
ON conversation(user_id, chatbot_id, created_at DESC);
