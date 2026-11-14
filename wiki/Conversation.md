# Conversation

Code location: `src/hr_minds/conversation/`.

The Conversation module is the central store for chat sessions. Any part of the platform can keep its chats here: a session is a `Conversation`, and every turn in it is a `Message`. This first version only stores and serves them; the assistant that replies is added on top later.

---

## 🏗️ Concepts

```text
User ──► Conversation (private to the user, inside one organization)
              │  optional context: ("job_posting", "12")
              ▼
          Message, Message, Message ...   (oldest first, ordered by id)
```

### Private to the owner
A conversation belongs to the user who started it, inside the organization that was active (`X-Org-Id`) at the time. Every query filters on both `org_id` and `user_id`, so:
- other members of the organization, **including the organization owner**, can't see it;
- the same user can't see it under a different organization's `X-Org-Id`;
- anything that isn't yours returns `404 Conversation not found`, exactly like a missing id, so existence isn't leaked.

This is deliberate: people will paste candidate details into chats.

### Context
`context_type` and `context_id` say what a chat is about, for example `("job_posting", "12")`. They are optional but go together (both or neither). There is no foreign key to other modules' tables, so this module stays independent, and a context can outlive the thing it points at. [List conversations](API-Endpoints#conversations) can be filtered by either.

### Only `user` messages come from clients
Everything stored in a conversation is later replayed to the model as history, so a client must not be able to forge an `assistant` or `tool` turn. The message request body has no `role` field and rejects unknown fields (`422`); the API always stores `user`. Assistant and tool messages are written only by server code through `conversation.services.conversation.add_message`.

---

## 🗄️ Database Schema

### `Conversation`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` | Primary key |
| `org_id` | `Integer` (FK → `organization.id`) | Organization the chat belongs to (CASCADE) |
| `user_id` | `Integer` (FK → `user.id`) | Owner (CASCADE) |
| `title` | `String(255)`, nullable | Optional label |
| `context_type` | `String(50)`, nullable | Kind of thing the chat is about |
| `context_id` | `String(64)`, nullable | Which one; a string so any module's ids fit |
| `last_message_at` | `DateTime(timezone=True)` | Creation time, then the time of the latest message; the list sorts by it |
| `created` / `modified` | `DateTime(timezone=True)` | Audit timestamps |

A check constraint requires `context_type` and `context_id` to be both set or both null.

### `Message`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` | Primary key; also the order within a conversation |
| `conversation_id` | `Integer` (FK → `conversation.id`) | Parent (CASCADE) |
| `role` | `String(20)` | `user`, `assistant` or `tool` |
| `content` | `Text`, nullable | Text of the turn; null for an assistant turn that is only tool calls |
| `tool_calls` | `JSONB`, nullable | Assistant turns: `[{"id", "name", "arguments"}]` |
| `tool_call_id` / `tool_name` | `String(100)`, nullable | Tool turns: which call this answers, and by which tool |
| `model` | `String(100)`, nullable | Assistant turns: which model answered |
| `input_tokens` / `output_tokens` | `Integer`, nullable | Assistant turns: usage; can't be rebuilt later |
| `created` / `modified` | `DateTime(timezone=True)` | Audit timestamps |

Messages use this provider-neutral shape on purpose: whichever model provider is used, an adapter converts to and from it, so switching provider needs no data migration.

**Deleting** a conversation removes its messages (`ON DELETE CASCADE`), and so does deleting the organization or the user.

---

## 🔐 RBAC & Permissions

The feature slug is `conversation`. Permissions gate who may use the chat at all; ownership (above) then decides which conversations they can see.

| Endpoint | Required Permission |
| :--- | :--- |
| `POST /api/v1/conversations` | `conversation:create` |
| `GET /api/v1/conversations` | `conversation:read` |
| `GET /api/v1/conversations/{id}` | `conversation:read` |
| `PATCH /api/v1/conversations/{id}` | `conversation:update` |
| `DELETE /api/v1/conversations/{id}` | `conversation:delete` |
| `GET /api/v1/conversations/{id}/messages` | `conversation:read` |
| `POST /api/v1/conversations/{id}/messages` | `conversation:create` |

After adding the feature, run `uv run python -m hr_minds.auth.cli sync-features` so roles can be granted these permissions. Organization owners have them automatically.

---

## 📏 Limits

- Message `content` is trimmed and must be 1 to 20,000 characters.
- `title` is at most 255 characters; `context_type` at most 50; `context_id` at most 64.
- Lists are [paginated](API-Endpoints#pagination): conversations default to 20 per page, messages to 50 (maximum 100 for both).

---

## 🔌 Using it from server code

```python
from hr_minds.conversation.models import MessageRole
from hr_minds.conversation.services import conversation as conversations

conversation = await conversations.get(db, org_id, user_id, conversation_id)  # 404 if not yours
await conversations.add_message(db, conversation, MessageRole.ASSISTANT, "Done.", model="...", output_tokens=42)
```

`add_message` appends the turn and moves `last_message_at` in one transaction. The service functions always take `org_id` and `user_id`, so there is no way to fetch a conversation without them.

For the HTTP specification see the [API Reference](API-Endpoints#conversations).
