import datetime
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.deps import get_db, get_graph
from app.core.middleware import CurrentUser, get_current_user
from app.langraph.graph import execute_graph
from app.model.chat import ChatRequest
from app.service.conversation_service import save_conversation_turn
from app.sql.queries import GET_CONVERSATION_BY_THREAD_ID


chat_router = APIRouter(tags=["chat"])


@chat_router.post("/message", summary="Chat with your data", description="Chat with your data")
async def chat(
    request: Request,
    query: ChatRequest,
    graph=Depends(get_graph),
    db=Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    start = time.perf_counter()
    try:
        query.user_id = user.sub
        query.auth_header = request.headers.get("authorization")
        result = await execute_graph(query, graph)

        response_time_ms = round((time.perf_counter() - start) * 1000, 2)
        saved = await save_conversation_turn(
            db,
            query,
            result,
            response_time_ms,
            chatbot_id=None,
            chatbot_name=query.bot_name or "",
            channel="app",
        )

        final_response = result.get("final_response", "")
        return {
            "thread_id": result.get("thread_id", ""),
            "final_response": final_response,
            "answer": final_response,
            "response_type": saved["response_type"],
            "document_ids": result.get("document_ids", []),
            "source_documents": result.get("source_documents", []),
            "metadata": {
                "conversation_id": saved["conversation_id"],
                "is_answered": saved["is_answered"],
                "answer_status": saved["answer_status"],
                "retrieval_response_time_ms": result.get("retrieval_response_time_ms", 0.0),
                "usage": result.get("token_usage", {}),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")


@chat_router.get(
    "/conversation",
    summary="Get conversation",
    description="Returns the conversation in chat UI format."
)
async def get_conversation(thread_id: str, db=Depends(get_db)):
    try:
        rows = await db.execute_async_query(
            GET_CONVERSATION_BY_THREAD_ID,
            {"thread_id": thread_id},
        )
        print(rows)

        if not rows or rows == []:
            return {
                "thread_id": thread_id,
                "total_messages": 0,
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
                "messages": [],
            }

        messages = []

        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        for row in rows:
     
            usage["prompt_tokens"] += row.get("prompt_tokens") or 0
            usage["completion_tokens"] += row.get("completion_tokens") or 0
            usage["total_tokens"] += row.get("total_tokens") or 0


            messages.append({
                "id": f"{row['id']}-user",
                "role": "user",
                "content": row["user_message"],
                "created_at": row["created_at"],
            })

  
            messages.append({
                "id": f"{row['id']}-assistant",
                "role": "assistant",
                "content": row["bot_message"],
                "created_at": row["created_at"],
                "metadata": {
                    "response_type": row["response_type"],
                    "model": row["model"],
                    "provider": row["provider"],
                    "response_time_ms": row["response_time_ms"],
                    "documents_retrieved": row["documents_retrieved"],
                    "chunks_retrieved": row["chunks_retrieved"],
                    "is_answered": row["is_answered"],
                    "answer_status": row["answer_status"],
                    "feedback": row["feedback"],
                },
                "usage": {
                    "prompt_tokens": row["prompt_tokens"],
                    "completion_tokens": row["completion_tokens"],
                    "total_tokens": row["total_tokens"],
                },
            })

        return {
            "thread_id": thread_id,
            "total_messages": len(messages),
            "usage": usage,
            "messages": messages,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching conversation: {e}",
        )


@chat_router.get("/conversations", summary="Get conversations", description="Returns all conversations for the user.",)
async def get_conversations(db=Depends(get_db), user=Depends(get_current_user)):

    try:
        user_id = user.sub
        conversations = await db.execute_async_query("SELECT DISTINCT ON (thread_id) * FROM conversation WHERE user_id = :user_id ORDER BY thread_id, created_at ASC;", {"user_id": user_id})
        result = []
        for conversation in conversations:
            result.append({
                "id": conversation["id"],
                "thread_id": conversation["thread_id"],
                "title": conversation["user_message"],
                "bot_message": conversation["bot_message"],
                "created_at": conversation["created_at"].isoformat() if isinstance(conversation["created_at"], datetime.datetime) else conversation["created_at"]
            })
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching conversations: {str(e)}")
