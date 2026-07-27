ADD_CONVERSATION = """
   INSERT INTO conversation ( id, thread_id, user_id, chatbot_id, chatbot_name, user_message, bot_message, response_type, model, provider, response_time_ms, prompt_tokens, completion_tokens, total_tokens, retrieval_response_time_ms, documents_retrieved, chunks_retrieved, confidence_score, is_answered, answer_status, feedback, feedback_comment, error_message, metadata)
   VALUES (:id, :thread_id, :user_id, :chatbot_id, :chatbot_name, :user_message, :bot_message, :response_type, :model, :provider, :response_time_ms, :prompt_tokens, :completion_tokens, :total_tokens, :retrieval_response_time_ms, :documents_retrieved, :chunks_retrieved, :confidence_score, :is_answered, :answer_status, :feedback, :feedback_comment, :error_message, :metadata)
"""

GET_CONVERSATION_BY_THREAD_ID = """
   SELECT * FROM conversation WHERE thread_id = :thread_id ORDER BY created_at ASC
"""