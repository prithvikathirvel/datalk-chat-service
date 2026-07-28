from app.langraph.schema import AgentState
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage
from app.langraph.constants.prompts import GENERAL_CHAT_PROMPT
from app.core.logging import logger
from app.langraph.utils.helper import (
    extract_token_usage,
    get_chatbot_prompt_parts,
    get_last_human_message,
    message_text,
    trim_messages,
)


async def general_chat(agent_state: AgentState, config: RunnableConfig):
    logger.info("[general_chat] Node entered")
    try:
        messages = agent_state["messages"]
        configurable = config.get("configurable", {})
        llm_service = configurable["llm"]
        user_message = get_last_human_message(messages)
        parts = get_chatbot_prompt_parts(configurable)
        logger.info(f"[general_chat] User query: {user_message!r}")

        llm_runnable = llm_service.get_llm(structured=False)
        system_prompt = GENERAL_CHAT_PROMPT.format(query=user_message, **parts)
        trimmed = trim_messages(messages, max_messages=10, max_tokens=2500)
        final_messages = [SystemMessage(content=system_prompt)] + trimmed

        logger.info(f"[general_chat] Invoking LLM with {len(trimmed)} history messages")
        response = await llm_service.ainvoke(llm_runnable, final_messages)
        response_text = message_text(response)
        logger.info(f"[general_chat] Response length: {len(response_text)} chars")
        return {
            "messages": [response],
            "final_response": response_text,
            "source_documents": [],
            "retrieved_texts": [],
            "document_ids": [],
            "token_usage": extract_token_usage(response),
        }
    except Exception as e:
        logger.error(f"[general_chat] Error: {e}")
        return {
            "messages": [],
            "final_response": "I'm sorry, I encountered an error processing your request. Please try again.",
            "source_documents": [],
            "retrieved_texts": [],
            "document_ids": [],
        }
