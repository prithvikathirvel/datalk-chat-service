from app.core.logging import logger
from app.langraph.schema import AgentState
from langchain_groq import ChatGroq
from app.langraph.utils.helper import get_last_human_message

llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)

async def check(agent_state: AgentState) -> AgentState:
    logger.info("[check] Node entered")
    try:
        messages = agent_state["messages"]
        logger.info(f"[check] Total messages in history: {len(messages)}, using last 5")
        trimmed = messages[-5:]
        response = await llm.ainvoke(trimmed)
        logger.info(f"[check] Response length: {len(response.content)} chars")
        return {"messages": [response], "final_response": response.content}
    except Exception as e:
        logger.error(f"[check] Error: {e}")
        raise