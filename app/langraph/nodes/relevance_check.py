from langchain_core.runnables import RunnableConfig
from app.core.logging import logger
from app.langraph.schema import AgentState
from langchain_core.messages import SystemMessage, AIMessage
from app.langraph.schema import RelevanceCheckOutput
from app.langraph.constants.prompts import RELEVANCE_PROMPT
from app.langraph.utils.helper import get_last_human_message

async def relevance_check(agent_state: AgentState, config: RunnableConfig):
    logger.info("[relevance_check] Node entered")
    try:
        messages = agent_state["messages"]
        llm_service = config["configurable"]["llm"]
        user_message = get_last_human_message(messages)
        logger.info(f"[relevance_check] User query: {user_message!r}")

        llm_runnable = llm_service.get_llm(structured=True, output_schema=RelevanceCheckOutput)
        system_prompt = RELEVANCE_PROMPT.format(user_msg=user_message)
        final_messages = [SystemMessage(content=system_prompt)] + messages

        logger.info("[relevance_check] Invoking LLM for relevance classification")
        response = await llm_service.ainvoke(llm_runnable, final_messages)
        relevance_result = response.relevance
        logger.info(f"[relevance_check] Result: {relevance_result!r}")
        return {"relevance": relevance_result}
    except Exception as e:
        logger.error(f"[relevance_check] Error: {e}")
        return {"relevance": "irrelevant"}