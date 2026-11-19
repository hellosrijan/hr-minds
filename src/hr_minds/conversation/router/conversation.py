from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import require
from hr_minds.auth.models import Membership
from hr_minds.conversation.agents.loop import get_chat_model, resume_turn, run_turn
from hr_minds.conversation.models import Conversation
from hr_minds.conversation.schemas import (
    ApprovalDecision,
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)
from hr_minds.conversation.services import conversation as conversation_service
from hr_minds.settings.db import get_db
from hr_minds.settings.features import FeatureSlug
from hr_minds.utils.pagination import PaginatedResponse

router = APIRouter(prefix="/conversations", tags=["Conversations"])

CONVERSATION = FeatureSlug.CONVERSATION


@router.post(
    "",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation",
)
async def create_conversation(
    data: ConversationCreate,
    membership: Membership = Depends(require(CONVERSATION, "create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new conversation session for the authenticated user and organization.

    Creates the conversation thread in the database. Optionally accepts a title
    and context metadata (`context_type` and `context_id`) to link the conversation
    to an entity (e.g., a job posting or candidate).
    """
    return await conversation_service.create(db, membership, data)


@router.get(
    "",
    response_model=PaginatedResponse[ConversationRead],
    summary="List your conversations (paginated, most recent activity first)",
)
async def list_conversations(
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    context_type: Annotated[str | None, Query(description="Only conversations about this kind of thing")] = None,
    context_id: Annotated[str | None, Query(description="Only conversations about this thing")] = None,
    membership: Membership = Depends(require(CONVERSATION, "read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ConversationRead]:
    """
    List conversations belonging to the current user in the active organization.

    Results are paginated and ordered by most recent message activity first (`last_message_at`).
    Optionally filter by `context_type` and `context_id`.
    """
    items, total = await conversation_service.list_for_user(
        db,
        membership.org_id,
        membership.user_id,
        page=page,
        page_size=page_size,
        context_type=context_type,
        context_id=context_id,
    )
    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.get("/{conversation_id}", response_model=ConversationRead, summary="Get a conversation")
async def get_conversation(
    conversation_id: int,
    membership: Membership = Depends(require(CONVERSATION, "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve details and metadata for a specific conversation by ID.

    Returns 404 if the conversation does not exist or belongs to another user or organization.
    """
    return await conversation_service.get(db, membership.org_id, membership.user_id, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationRead, summary="Rename a conversation")
async def rename_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    membership: Membership = Depends(require(CONVERSATION, "update")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a conversation's title.

    Modifies the title field; existing message turns and context metadata remain unchanged.
    """
    return await conversation_service.rename(db, membership.org_id, membership.user_id, conversation_id, data)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation and its messages",
)
async def delete_conversation(
    conversation_id: int,
    membership: Membership = Depends(require(CONVERSATION, "delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently delete a conversation and all its associated messages.

    All stored messages in this thread are deleted via database cascade.
    """
    await conversation_service.delete(db, membership.org_id, membership.user_id, conversation_id)


@router.get(
    "/{conversation_id}/messages",
    response_model=PaginatedResponse[MessageRead],
    summary="List a conversation's messages (paginated, oldest first)",
)
async def list_messages(
    conversation_id: int,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 50,
    membership: Membership = Depends(require(CONVERSATION, "read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MessageRead]:
    """
    List messages in a conversation in chronological order (oldest first).

    Returns paginated turns including user messages, assistant responses, tool calls, and tool outputs.
    """
    items, total = await conversation_service.list_messages(
        db, membership.org_id, membership.user_id, conversation_id, page=page, page_size=page_size
    )
    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


# One callable per permission so FastAPI caches it: the pre-stream dependency and the
# endpoint share a single permission check and Membership.
can_send = require(CONVERSATION, "create")


async def _conversation_to_run(
    conversation_id: int,
    data: MessageCreate,
    membership: Membership = Depends(can_send),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    # Runs before the SSE stream opens, so these are real HTTP errors, not a broken stream:
    # 404 for an unknown conversation, 409 if the assistant is still answering in it.
    # It takes `data` on purpose: FastAPI doesn't call a dependency whose own parameters
    # failed validation, so a bad body (422) is rejected BEFORE the run is claimed.
    conversation = await conversation_service.get(db, membership.org_id, membership.user_id, conversation_id)
    await conversation_service.start_run(db, conversation)
    return conversation


@router.post(
    "/{conversation_id}/messages",
    response_class=EventSourceResponse,
    summary="Send a message and stream the assistant's reply",
)
async def send_message(
    data: MessageCreate,
    conversation: Conversation = Depends(_conversation_to_run),
    membership: Membership = Depends(can_send),
    db: AsyncSession = Depends(get_db),
    model: ChatOpenAI | None = Depends(get_chat_model),
) -> AsyncIterable[ServerSentEvent]:
    """
    Save your message, then run the assistant and stream what it does as server-sent events:
    - `message`     — your saved message, then the assistant's final answer
    - `tool_call`   — the assistant asked for one or more tools
    - `tool_result` — one tool finished
    - `done`        — the turn ended normally
    - `error`       — the turn ended early (the saved messages stay)
    """
    try:
        async for event in run_turn(db, membership, conversation, model, data.content):
            yield ServerSentEvent(event=event.pop("event"), data=event)
    finally:
        await conversation_service.finish_run(db, conversation)


# Conversation waiting for User Approval.
async def _conversation_for_approval(
        conversation_id: int,
        data: ApprovalDecision,
        membership: Membership = Depends(can_send),
        db: AsyncSession = Depends(get_db),
) -> Conversation:
    conversation = await conversation_service.get(db=db, org_id=membership.org_id, user_id=membership.user_id, conversation_id=conversation_id)
    await conversation_service.start_run(db=db, conversation=conversation)
    return conversation

@router.post('/{conversation_id}/approvals', response_class=EventSourceResponse, summary='Approval or Reject a pending tool execution')
async def submit_approval(
    data: ApprovalDecision, 
    conversation: Conversation = Depends(_conversation_for_approval), 
    membership: Membership = Depends(can_send), 
    db: AsyncSession = Depends(get_db), 
    model: ChatOpenAI | None = Depends(get_chat_model)
    ) -> AsyncIterable[ServerSentEvent]:
    """
    Resume an interrupted assistant turn.
    - If approved: executes the tool and streams the assistant's reply.
    - If rejected: skips the tool execution and lets the assistant respond accordingly.
    """
    try:
        async for event in resume_turn(db, membership, conversation, model, data.approve):
            yield ServerSentEvent(event=event.pop('event'), data=event)
    finally:
        await conversation_service.finish_run(db=db, conversation=conversation)
