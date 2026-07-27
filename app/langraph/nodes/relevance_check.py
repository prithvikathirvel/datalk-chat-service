from langchain_core.runnables import RunnableConfig
from app.core.logging import logger
from app.langraph.schema import AgentState
from langchain_core.messages import SystemMessage, HumanMessage
from app.langraph.schema import RelevanceCheckOutput
from app.langraph.constants.prompts import RELEVANCE_PROMPT
from app.langraph.utils.helper import extract_token_usage

async def relevance_check(agent_state: AgentState, config: RunnableConfig):
    logger.info("[relevance_check] Node entered")
    try:
        messages = agent_state["messages"]
        llm_service = config["configurable"]["llm"]
        standalone_query = agent_state.get("standalone_query") or ""
        logger.info(f"[relevance_check] Standalone query: {standalone_query!r}")

        # include_raw=True returns {"raw": AIMessage, "parsed": schema} so we
        # can read usage_metadata from the raw message (structured output strips it)
        llm_runnable = llm_service.get_llm(
            structured=True, output_schema=RelevanceCheckOutput, include_raw=True
        )

        system_prompt = RELEVANCE_PROMPT.format(user_msg=standalone_query)
        final_messages = [SystemMessage(content=system_prompt), HumanMessage(content=standalone_query)]

        logger.info("[relevance_check] Invoking LLM for relevance classification")
        response = await llm_service.ainvoke(llm_runnable, final_messages)
        relevance_result = response["parsed"].relevance
        logger.info(f"[relevance_check] Result: {relevance_result!r}")
        return {"relevance": relevance_result, "token_usage": extract_token_usage(response["raw"])}
    except Exception as e:
        logger.error(f"[relevance_check] Error: {e}")
        return {"relevance": "irrelevant"}