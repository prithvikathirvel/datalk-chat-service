-- Migration: Per-chatbot document source scoping (RAG filtering).
--
-- Adds the `embed_config_sources` junction table so each chatbot (embed
-- config) can optionally be restricted to search only a subset of the
-- owning user's ingested documents. If a config has no rows here, its
-- widget searches the user's entire document corpus (no filter applied) —
-- see app/langraph/nodes/fetch_data.py and app/api/v1/embed.py.
--
-- Depends on 0001_embed_configs.sql (embed_configs table).
-- Safe to re-run.

CREATE TABLE IF NOT EXISTS embed_config_sources (
    config_id         UUID NOT NULL REFERENCES embed_configs(id) ON DELETE CASCADE,
    document_id       TEXT NOT NULL,          -- matches DocumentFile.id from ingestion backend
    document_filename TEXT NOT NULL,          -- denormalized from DocumentFile.filename
    added_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (config_id, document_id)
);

CREATE INDEX IF NOT EXISTS embed_config_sources_config_id_idx ON embed_config_sources(config_id);
