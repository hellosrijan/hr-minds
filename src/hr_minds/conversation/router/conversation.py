from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import require
from hr_minds.auth.models import Membership
from hr_minds.conversation.models import MessageRole
from hr_minds.conversation.schemas import (
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
    return await conversation_service.get(db, membership.org_id, membership.user_id, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationRead, summary="Rename a conversation")
async def rename_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    membership: Membership = Depends(require(CONVERSATION, "update")),
    db: AsyncSession = Depends(get_db),
):
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
    items, total = await conversation_service.list_messages(
        db, membership.org_id, membership.user_id, conversation_id, page=page, page_size=page_size
    )
    return PaginatedResponse.create(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a user message",
)
async def add_message(
    conversation_id: int,
    data: MessageCreate,
    membership: Membership = Depends(require(CONVERSATION, "create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Store a message you send. For now this only records it; the assistant's reply
    will come from this same endpoint once the agent is added.
    """
    conversation = await conversation_service.get(db, membership.org_id, membership.user_id, conversation_id)
    return await conversation_service.add_message(db, conversation, MessageRole.USER, data.content)
