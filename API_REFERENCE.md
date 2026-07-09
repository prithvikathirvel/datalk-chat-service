# RAG Chat Service — API Reference

Base URL: `{VERSION_PREFIX}` (e.g. `/api/v1`)

All protected endpoints require a **Bearer JWT token** in the `Authorization` header.

---

## Authentication

Every request to a protected endpoint must include:

```
Authorization: Bearer <jwt_token>
```

The token is decoded server-side; the `sub` claim is used as the `user_id`.

---

## Endpoints

### 1. Health Check

```
GET /health
```

No authentication required.

**Response `200`**

```json
{
  "status": "ok",
  "version": "/api/v1"
}
```

---

### 2. Chat

```
POST /chat/chat
```

**Auth:** Required

**Request Body** (`application/json`)

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | `string` | Yes | The user's message. Must not contain `<script>` tags or null bytes. |
| `model` | `string` | No | LLM model name to use. Defaults to server-configured default. |
| `thread_id` | `string` | No | Conversation thread ID. If omitted, a new UUID is generated (starts a new conversation). Pass the returned `thread_id` in subsequent messages to continue a conversation. |

> `user_id` is injected server-side from the JWT — do **not** send it.

**Request Example**

```json
{
  "message": "What does the uploaded contract say about termination?",
  "thread_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

**Response `200`**

| Field | Type | Description |
|---|---|---|
| `thread_id` | `string` | Thread ID for this conversation. Store and reuse to continue the chat. |
| `final_response` | `string` | The assistant's reply. |

```json
{
  "thread_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "final_response": "The contract states that either party may terminate with 30 days written notice..."
}
```

**Error Responses**

| Status | Description |
|---|---|
| `401` | Missing or invalid JWT token |
| `422` | Validation error (e.g. message contains script tags) |

---

### 3. Get Conversation

```
GET /chat/get-conversation?thread_id={thread_id}
```

**Auth:** Required

**Query Parameter**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `thread_id` | `string` | Yes | The thread ID returned from the `/chat` endpoint. |

**Response `200`**

```json
{
  "success": true,
  "thread_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "message_count": 4,
  "conversation": [
    {
      "id": 1,
      "role": "user",
      "type": "human",
      "content": "What does the contract say about termination?",
      "name": null,
      "tool_call_id": null,
      "response_metadata": {},
      "additional_kwargs": {}
    },
    {
      "id": 2,
      "role": "assistant",
      "type": "ai",
      "content": "The contract states that either party may terminate...",
      "name": null,
      "tool_call_id": null,
      "response_metadata": {},
      "additional_kwargs": {}
    }
  ],
  "checkpoint": {
    "checkpoint_id": "abc123",
    "checkpoint_ns": ""
  },
  "metadata": {},
  "created_at": "2026-07-07T17:59:58.000000",
  "next": [],
  "tasks": []
}
```

**Conversation message fields**

| Field | Type | Description |
|---|---|---|
| `id` | `integer` | 1-based position in the conversation |
| `role` | `string` | `"user"`, `"assistant"`, `"system"`, or `"tool"` |
| `type` | `string` | LangChain message type (`"human"`, `"ai"`, `"system"`, `"tool"`) |
| `content` | `string` | Message text content |
| `name` | `string \| null` | Tool/function name, if applicable |
| `tool_call_id` | `string \| null` | ID of the associated tool call, if applicable |
| `response_metadata` | `object` | LLM provider metadata (token counts, finish reason, etc.) |
| `additional_kwargs` | `object` | Extra provider-specific fields |

**Error Responses**

| Status | Description |
|---|---|
| `401` | Missing or invalid JWT token |
| `404` | Thread ID not found or unable to load |

---

## Conversation Flow

```
1. POST /chat/chat  (no thread_id)
   → returns thread_id + first response

2. POST /chat/chat  (pass thread_id from step 1)
   → continues the conversation, returns updated thread_id + response

3. GET /chat/get-conversation?thread_id=...
   → retrieves full message history at any time
```

---

## Notes

- **New conversation**: omit `thread_id` — the server creates one and returns it.
- **Continue conversation**: always pass the `thread_id` from the previous response.
- Responses are either RAG-based (from indexed documents) or general LLM answers — the routing is transparent to the frontend.
- The `response_metadata` object in conversation messages may include token usage and finish reason from the LLM provider, useful for debugging.
