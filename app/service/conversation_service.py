import json
import re
import uuid
from typing import Any

from app.core.config import config
from app.schema.model import Conversation
from app.sql.queries import ADD_CONVERSATION_WITH_QUESTION_STATS


def _normalize_question(question: str) -> str:
    text = re.sub(r"[^\w\s]", " ", (question or "").lower())
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(
        r"^(please|can you|could you|tell me|i want to know|i need to know|what is|what are|how do i|how can i|do you|does it|is there|can i)\s+",
        "",
        text,
    )
    text = re.sub(r"^(the|a|an)\s+", "", text)
    return text[:500] or "empty question"


async def save_conversation_turn(
    db,
    query,
    result: dict[str, Any],
    response_time_ms: float,
    *,
    chatbot_id: str | None = None,
    chatbot_name: str | None = None,
    channel: str = "app",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one chat turn and update top-question stats in the same DB call."""
    is_rag = result.get("relevance") == "relevant"
    response_type = "rag" if is_rag else "general_chat"
    is_answered = (not is_rag) or bool(result.get("retrieved_texts"))
    standalone_query = (result.get("standalone_query") or query.message or "").strip()
    conversation_id = uuid.uuid4()

    meta = {
        "channel": channel,
        "response_type": "rag" if is_rag else "general",
        "document_ids": result.get("document_ids", []),
        "source_documents": result.get("source_documents", []),
        **(metadata or {}),
    }

    conversation = Conversation(
        id=conversation_id,
        thread_id=result.get("thread_id", ""),
        user_id=query.user_id,
        chatbot_id=chatbot_id,
        chatbot_name=chatbot_name or query.bot_name or "",
        user_message=query.message,
        rewritten_query=standalone_query,
        bot_message=result.get("final_response", ""),
        response_type=response_type,
        final_node="rag_response" if is_rag else "general_chat",
        model=result.get("model", config.DEFAULT_LLM_MODEL),
        provider="provider",
        response_time_ms=int(response_time_ms),
        prompt_tokens=int(result.get("token_usage", {}).get("prompt_tokens", 0)),
        completion_tokens=int(result.get("token_usage", {}).get("completion_tokens", 0)),
        total_tokens=int(result.get("token_usage", {}).get("total_tokens", 0)),
        retrieval_response_time_ms=result.get("retrieval_response_time_ms", 0.0),
        documents_retrieved=len(result.get("source_documents", [])),
        chunks_retrieved=len(result.get("retrieved_texts", [])),
        confidence_score=0.0,
        is_answered=is_answered,
        answer_status="answered" if is_answered else "unanswered",
        feedback=0,
        feedback_comment="",
        error_message="",
        metadata=json.dumps(meta),
    )

    params = conversation.model_dump(mode="python")
    params["analytics_question"] = standalone_query[:1000] or query.message[:1000]
    params["normalized_question"] = _normalize_question(standalone_query or query.message)
    params["question_similarity_threshold"] = config.QUESTION_SIMILARITY_THRESHOLD
    await db.execute_async_query(ADD_CONVERSATION_WITH_QUESTION_STATS, params)

    return {
        "conversation_id": str(conversation_id),
        "response_type": meta["response_type"],
        "is_answered": is_answered,
        "answer_status": conversation.answer_status,
    }
