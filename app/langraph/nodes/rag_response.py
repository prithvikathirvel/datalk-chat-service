from langchain_core.runnables import RunnableConfig
from app.core.logging import logger
from app.langraph.schema import AgentState
from langchain_core.messages import SystemMessage, AIMessage
from app.langraph.constants.prompts import RAG_RESPONSE_PROMPT
from app.langraph.utils.helper import trim_messages


async def rag_response(agent_state: AgentState, config: RunnableConfig):
    logger.info("[rag_response] Node entered")
    try:
        messages = agent_state["messages"]
        retrieved_texts = agent_state.get("retrieved_texts", [])
        source_documents = agent_state.get("source_documents", [])
        standalone_query = agent_state.get("standalone_query", "")
        logger.info(f"[rag_response] Context chunks: {len(retrieved_texts)}, source docs: {len(source_documents)}")

        llm_service = config["configurable"]["llm"]
        llm_runnable = llm_service.get_llm(structured=False)

        logger.info(f"[rag_response] Standalone query: {standalone_query!r}")
        context = "\n\n---\n\n".join(retrieved_texts) if retrieved_texts else "No context retrieved."

        system_prompt = RAG_RESPONSE_PROMPT.format(query=standalone_query, context=context)
        trimmed = trim_messages(messages, max_messages=10)
        final_messages = [SystemMessage(content=system_prompt)] + trimmed

        logger.info(f"[rag_response] Invoking LLM with {len(trimmed)} history messages")
        response = await llm_service.ainvoke(llm_runnable, final_messages)
        logger.info(f"[rag_response] Response length: {len(response.content)} chars")

        return {
            "messages": [AIMessage(content=response.content)],
            "final_response": response.content,
            "source_documents": source_documents,
        }
    except Exception as e:
        logger.error(f"[rag_response] Error: {e}")
        return {"messages": [], "final_response": "I'm sorry, I encountered an error generating a response. Please try again."}