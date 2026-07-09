from fastapi import APIRouter, Depends,HTTPException
from app.api.v1.deps import get_graph
from app.model.chat import ChatRequest
from app.core.middleware import get_current_user
from app.langraph.graph import execute_graph
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
import datetime


chat_router = APIRouter(prefix="/chat", tags=["chat"])



@chat_router.post("/chat", summary="Chat with your data", description="Chat with your data")
async def chat(user_input:ChatRequest, user = Depends(get_current_user), graph = Depends(get_graph)):
    user_id = user.get("sub","")
    user_input.user_id = user_id
    result = await execute_graph(user_input, graph)
    final_result = {"thread_id": result.get("thread_id", ""), "final_response": result.get("final_response", "")}
    return final_result


@chat_router.get("/get-conversation", summary="Get conversation by thread ID", description="Returns the complete conversation for a thread.",)
async def get_conversation( thread_id: str, graph=Depends(get_graph),
):
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    try:
        state = await graph.aget_state(config)

    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Unable to load thread: {str(e)}"
        )

    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Thread not found."
        )

    messages = state.values.get("messages", [])

    conversation = []

    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        elif isinstance(msg, SystemMessage):
            role = "system"
        elif isinstance(msg, ToolMessage):
            role = "tool"
        else:
            role = msg.type

        conversation.append(
            {
                "id": i + 1,
                "role": role,
                "type": msg.type,
                "content": msg.content,
                "name": getattr(msg, "name", None),
                "tool_call_id": getattr(msg, "tool_call_id", None),
                "response_metadata": getattr(msg, "response_metadata", {}),
                "additional_kwargs": getattr(msg, "additional_kwargs", {}),
            }
        )

    return {
        "success": True,
        "thread_id": thread_id,
        "message_count": len(conversation),
        "conversation": conversation,
        "checkpoint": {
            "checkpoint_id": state.config["configurable"].get("checkpoint_id"),
            "checkpoint_ns": state.config["configurable"].get("checkpoint_ns"),
        },
        "metadata": state.metadata,
        "created_at": (
            state.created_at.isoformat()
            if isinstance(state.created_at, datetime.datetime)
            else state.created_at
        ),
        "next": state.next,
        "tasks": [
            task.model_dump() if hasattr(task, "model_dump") else str(task)
            for task in state.tasks
        ],
    }

    