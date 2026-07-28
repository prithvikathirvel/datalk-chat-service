-- Migration: private chatbot context prompt for LangGraph.
--
-- `context_prompt` is owner-configured guidance/context used server-side by
-- the chat graph. It is intentionally not returned by the public widget config.

ALTER TABLE embed_configs
ADD COLUMN IF NOT EXISTS context_prompt TEXT;
