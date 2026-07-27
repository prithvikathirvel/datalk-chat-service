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

---

## Embed Widget API (Chatbot Embed Configs & API Keys)

Replaces the previous flat-file `embed-configs.json` approach with real
Postgres-backed storage (`embed_configs`, `api_keys`, `embed_feedback`
tables — see `app/sql/migrations/0001_embed_configs.sql`).

There are two families of routes, mounted under `{VERSION_PREFIX}/embed`:

- **Owner-authenticated** routes (same Cognito JWT auth as the rest of the
  API, via the `x-amzn-request-context` header / `get_current_user`):
  used by the first-party dashboard to manage chatbots.
- **Public, API-key-authenticated** routes: used by the embeddable widget
  running on third-party sites. These never see a Cognito session — they
  authenticate with a scoped API key instead.

### API Key Format

`dk_live_` + 32 random bytes, base64url-encoded (~51 chars total), e.g.
`dk_live_aB3xQp7mNwRtYu9vKs2dFe6hCjLnOiPqZ4bGcM8W`.

The raw key is only ever returned **once** — at creation time
(`POST /embed/configs`) or key rotation time
(`POST /embed/configs/{bot_id}/rotate-key`). Only its SHA-256 hash and a
12-char display prefix (e.g. `dk_live_aB3x`) are persisted.

### Owner-authenticated Endpoints

| Method | Route | Description |
|---|---|---|
| `POST` | `/embed/configs` | Create a chatbot config. Also generates its first API key. Returns `{ config, api_key: { api_key: "<raw, shown once>", ... } }`. |
| `GET` | `/embed/configs` | List all configs owned by the authenticated user. |
| `GET` | `/embed/configs/{bot_id}` | Get a single owned config. |
| `PUT` | `/embed/configs/{bot_id}` | Partial update. Omitted fields are left unchanged. Does **not** rotate the API key. |
| `DELETE` | `/embed/configs/{bot_id}` | Delete a config. Cascades to delete its `api_keys` and `embed_feedback` rows. |
| `POST` | `/embed/configs/{bot_id}/rotate-key` | Revokes the currently active key(s) and issues a new one. Returns the new raw key once. |
| `GET` | `/embed/feedback` | List feedback across all of the authenticated user's chatbots. |

### Public Endpoints (widget-facing, no Cognito session)

Authenticate with either the `X-Api-Key` header, or `?apiKey=` query param
(used by `/embed/script`, since a `<script src>` tag can't set headers).

| Method | Route | Description |
|---|---|---|
| `GET` | `/embed/config` | Fetch the sanitized public config for the widget (no `user_id` or other internal fields). |
| `POST` | `/embed/chat` | Send a chat message from the widget. Proxies to the same LangGraph pipeline as `/message`, scoped to the chatbot's API key. |
| `POST` | `/embed/feedback` | Submit widget feedback (`reason` one of `not_helpful`, `needs_human`, `gap_detected`). |
| `GET` | `/embed/script` | Bootstrap payload (`{ config, endpoints }`) for the embeddable `<script>` loader. |

**Validation performed on every public request** (see
`app/core/embed_auth.py::validate_api_key`):

1. Read raw key from `X-Api-Key` header (or `?apiKey=`).
2. Hash with SHA-256 and look up in `api_keys` joined with `embed_configs`.
3. Reject if the key is inactive / revoked / expired.
4. Reject if the owning config has `is_active = false`.
5. Check the request's `Origin` header against `allowed_origins` (empty list
   = unrestricted, `*` = wildcard).
6. Update `last_used_at` on the key (best-effort).

Public embed routes get relaxed CORS (see `app/core/embed_cors.py`) so
browsers on third-party origins can call them directly — actual
authorization is still enforced by the API key + origin check above, not by
CORS.

### Per-Chatbot Document Sources (RAG Scoping)

By default a chatbot's widget searches the *entire* document library owned
by the user who created it. You can optionally restrict a chatbot to a
specific subset of documents via the `embed_config_sources` junction table
(`app/sql/migrations/0002_embed_config_sources.sql`).

**Rule**: if a config has zero rows in `embed_config_sources` → unrestricted
(searches all documents). If it has one or more rows → RAG retrieval is
restricted to only those `document_id` values.

| Method | Route | Auth | Description |
|---|---|---|---|
| `GET` | `/embed/configs/{bot_id}/sources` | Session | List documents assigned to this chatbot. |
| `POST` | `/embed/configs/{bot_id}/sources` | Session | Upsert one or more `{ document_id, document_filename }` entries. Body: `{ "documents": [...] }`. |
| `DELETE` | `/embed/configs/{bot_id}/sources/{document_id}` | Session | Remove a single source document. |
| `DELETE` | `/embed/configs/{bot_id}/sources` | Session | Clear all sources — reverts the chatbot to "all documents" mode. |

`GET /embed/configs` and `GET /embed/configs/{bot_id}` now also return a
`source_document_ids: string[]` field (empty = unrestricted). This field is
intentionally **omitted** from `EmbedConfigPublic` — the public widget
doesn't need to know which documents back its answers.

**How the restriction is enforced end-to-end:**

1. `POST /embed/chat` resolves the calling API key to its `config_id`, then
   looks up `embed_config_sources` for that config
   (`app/api/v1/embed.py::_get_source_document_ids`).
2. If sources exist, they're passed as `ChatRequest.source_document_ids`
   into the LangGraph pipeline (`app/langraph/graph.py::execute_graph`,
   propagated via `graph_config["configurable"]`).
3. `app/langraph/nodes/fetch_data.py` forwards `source_document_ids` to
   `app/service/rag_service.py::fetch_relevant_chunks`, which requests
   pre-retrieval filtering from the RAG service (`document_ids` query
   param — adjust the param name once the RAG service's actual filter
   contract is confirmed).
4. As defense-in-depth, `fetch_data` *also* discards any returned chunk
   whose `document_id` isn't in the allowed set, so a chatbot scoped to
   specific documents can never leak content from documents outside that
   scope even if the RAG service doesn't yet support the filter.
5. The authenticated `/message` endpoint is unaffected — it never sets
   `source_document_ids`, so it continues to search the full corpus exactly
   as before.

### Migrations

Run once against the configured Postgres database:

```
python -m scripts.apply_migrations
```

This applies, in order:
- `app/sql/migrations/0001_embed_configs.sql` — creates `embed_configs`,
  `api_keys`, and `embed_feedback`.
- `app/sql/migrations/0002_embed_config_sources.sql` — creates
  `embed_config_sources` for per-chatbot RAG scoping.

Both are idempotent (`CREATE TABLE IF NOT EXISTS`).

