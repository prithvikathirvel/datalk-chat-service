ADD_CONVERSATION = """
   INSERT INTO conversation ( id, thread_id, user_id, chatbot_id, chatbot_name, user_message, bot_message, response_type, model, provider, response_time_ms, prompt_tokens, completion_tokens, total_tokens, retrieval_response_time_ms, documents_retrieved, chunks_retrieved, confidence_score, is_answered, answer_status, feedback, feedback_comment, error_message, metadata)
   VALUES (:id, :thread_id, :user_id, :chatbot_id, :chatbot_name, :user_message, :bot_message, :response_type, :model, :provider, :response_time_ms, :prompt_tokens, :completion_tokens, :total_tokens, :retrieval_response_time_ms, :documents_retrieved, :chunks_retrieved, :confidence_score, :is_answered, :answer_status, :feedback, :feedback_comment, :error_message, :metadata)
"""

GET_CONVERSATION_BY_THREAD_ID = """
   SELECT * FROM conversation WHERE thread_id = :thread_id ORDER BY created_at ASC
"""

# ──────────────────────────────────────────────
# Embed configs
# ──────────────────────────────────────────────

INSERT_EMBED_CONFIG = """
    INSERT INTO embed_configs (
        id, user_id, bot_name, bot_description,
        welcome_message, fallback_message, suggested_questions,
        primary_color, chat_background, position, launcher_label,
        launcher_style, avatar_initials, border_radius_style, widget_shadow,
        font_family, show_powered_by, allowed_origins, collect_visitor_email,
        is_active, model
    )
    VALUES (
        :id, :user_id, :bot_name, :bot_description,
        :welcome_message, :fallback_message, :suggested_questions,
        :primary_color, :chat_background, :position, :launcher_label,
        :launcher_style, :avatar_initials, :border_radius_style, :widget_shadow,
        :font_family, :show_powered_by, :allowed_origins, :collect_visitor_email,
        :is_active, :model
    )
    RETURNING *
"""

GET_EMBED_CONFIGS_BY_USER = """
    SELECT * FROM embed_configs WHERE user_id = :user_id ORDER BY created_at DESC
"""

GET_EMBED_CONFIG_BY_ID = """
    SELECT * FROM embed_configs WHERE id = :id
"""

GET_EMBED_CONFIG_BY_ID_FOR_USER = """
    SELECT * FROM embed_configs WHERE id = :id AND user_id = :user_id
"""

UPDATE_EMBED_CONFIG = """
    UPDATE embed_configs
    SET
        bot_name = :bot_name,
        bot_description = :bot_description,
        welcome_message = :welcome_message,
        fallback_message = :fallback_message,
        suggested_questions = :suggested_questions,
        primary_color = :primary_color,
        chat_background = :chat_background,
        position = :position,
        launcher_label = :launcher_label,
        launcher_style = :launcher_style,
        avatar_initials = :avatar_initials,
        border_radius_style = :border_radius_style,
        widget_shadow = :widget_shadow,
        font_family = :font_family,
        show_powered_by = :show_powered_by,
        allowed_origins = :allowed_origins,
        collect_visitor_email = :collect_visitor_email,
        is_active = :is_active,
        model = :model,
        updated_at = NOW()
    WHERE id = :id AND user_id = :user_id
    RETURNING *
"""

DELETE_EMBED_CONFIG = """
    DELETE FROM embed_configs WHERE id = :id AND user_id = :user_id
    RETURNING id
"""

# ──────────────────────────────────────────────
# API keys
# ──────────────────────────────────────────────

INSERT_API_KEY = """
    INSERT INTO api_keys (id, config_id, user_id, key_hash, key_prefix, name, expires_at)
    VALUES (:id, :config_id, :user_id, :key_hash, :key_prefix, :name, :expires_at)
    RETURNING *
"""

GET_ACTIVE_API_KEYS_BY_CONFIG = """
    SELECT * FROM api_keys
    WHERE config_id = :config_id AND revoked_at IS NULL
    ORDER BY created_at DESC
"""

REVOKE_ACTIVE_API_KEYS_FOR_CONFIG = """
    UPDATE api_keys
    SET is_active = FALSE, revoked_at = NOW()
    WHERE config_id = :config_id AND is_active = TRUE AND revoked_at IS NULL
    RETURNING id
"""

GET_CONFIG_AND_KEY_BY_KEY_HASH = """
    SELECT
        ak.id AS api_key_id,
        ak.is_active AS api_key_is_active,
        ak.expires_at AS api_key_expires_at,
        ak.revoked_at AS api_key_revoked_at,
        ec.*
    FROM api_keys ak
    JOIN embed_configs ec ON ec.id = ak.config_id
    WHERE ak.key_hash = :key_hash
"""

UPDATE_API_KEY_LAST_USED = """
    UPDATE api_keys SET last_used_at = NOW() WHERE id = :id
"""

# ──────────────────────────────────────────────
# Embed feedback
# ──────────────────────────────────────────────

INSERT_EMBED_FEEDBACK = """
    INSERT INTO embed_feedback (
        id, config_id, user_id, thread_id, question, answer,
        visitor_email, page_url, parent_origin, reason
    )
    VALUES (
        :id, :config_id, :user_id, :thread_id, :question, :answer,
        :visitor_email, :page_url, :parent_origin, :reason
    )
    RETURNING *
"""

GET_EMBED_FEEDBACK_BY_USER = """
    SELECT * FROM embed_feedback WHERE user_id = :user_id ORDER BY created_at DESC
"""

GET_EMBED_FEEDBACK_BY_CONFIG = """
    SELECT * FROM embed_feedback WHERE config_id = :config_id ORDER BY created_at DESC
"""

# ──────────────────────────────────────────────
# Embed config sources (per-chatbot RAG scoping — Phase 5)
# ──────────────────────────────────────────────

UPSERT_EMBED_CONFIG_SOURCE = """
    INSERT INTO embed_config_sources (config_id, document_id, document_filename)
    VALUES (:config_id, :document_id, :document_filename)
    ON CONFLICT (config_id, document_id)
    DO UPDATE SET document_filename = EXCLUDED.document_filename
    RETURNING *
"""

GET_EMBED_CONFIG_SOURCES = """
    SELECT * FROM embed_config_sources WHERE config_id = :config_id ORDER BY added_at DESC
"""

GET_EMBED_CONFIG_SOURCE_IDS = """
    SELECT document_id FROM embed_config_sources WHERE config_id = :config_id
"""

DELETE_EMBED_CONFIG_SOURCE = """
    DELETE FROM embed_config_sources
    WHERE config_id = :config_id AND document_id = :document_id
    RETURNING document_id
"""

DELETE_ALL_EMBED_CONFIG_SOURCES = """
    DELETE FROM embed_config_sources WHERE config_id = :config_id
    RETURNING document_id
"""