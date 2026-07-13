from langchain_core.runnables import RunnableConfig
from app.core.logging import logger
from app.langraph.schema import AgentState
from langchain_core.messages import SystemMessage
from app.langraph.schema import RelevanceCheckOutput
from app.langraph.constants.prompts import RELEVANCE_PROMPT

async def relevance_check(agent_state: AgentState, config: RunnableConfig):
    logger.info("[relevance_check] Node entered")
    try:
        messages = agent_state["messages"]
        llm_service = config["configurable"]["llm"]
        # Use the rewritten standalone query for accurate classification
        standalone_query = agent_state.get("standalone_query") or ""
        logger.info(f"[relevance_check] Standalone query: {standalone_query!r}")

        llm_runnable = llm_service.get_llm(structured=True, output_schema=RelevanceCheckOutput)
        # Classification only needs the query — passing conversation history confuses
        # tool-calling models and causes structured output failures on Groq
        system_prompt = RELEVANCE_PROMPT.format(user_msg=standalone_query)
        final_messages = [SystemMessage(content=system_prompt)]

        logger.info("[relevance_check] Invoking LLM for relevance classification")
        response = await llm_service.ainvoke(llm_runnable, final_messages)
        relevance_result = response.relevance
        logger.info(f"[relevance_check] Result: {relevance_result!r}")
        return {"relevance": relevance_result}
    except Exception as e:
        logger.error(f"[relevance_check] Error: {e}")
        return {"relevance": "irrelevant"}