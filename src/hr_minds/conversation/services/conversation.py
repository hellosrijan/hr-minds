from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import Membership
from hr_minds.conversation.exceptions import ConversationNotFound
from hr_minds.conversation.models import Conversation, Message, MessageRole
from hr_minds.conversation.schemas import ConversationCreate, ConversationUpdate


async def create(db: AsyncSession, membership: Membership, data: ConversationCreate) -> Conversation:
    conversation = Conversation(org_id=membership.org_id, user_id=membership.user_id, **data.model_dump())
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)  # server defaults: created, modified, last_message_at
    return conversation


async def get(db: AsyncSession, org_id: int, user_id: int, conversation_id: int) -> Conversation:
    # Someone else's conversation looks exactly like a missing one.
    conversation = await Conversation.get(db, org_id, user_id, conversation_id)
    if conversation is None:
        raise ConversationNotFound()
    return conversation


async def list_for_user(
    db: AsyncSession,
    org_id: int,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    context_type: str | None = None,
    context_id: str | None = None,
) -> tuple[list[Conversation], int]:
    return await Conversation.list_for_user(
        db, org_id, user_id, page=page, page_size=page_size, context_type=context_type, context_id=context_id
    )


async def rename(
    db: AsyncSession, org_id: int, user_id: int, conversation_id: int, data: ConversationUpdate
) -> Conversation:
    conversation = await get(db, org_id, user_id, conversation_id)
    conversation.title = data.title
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def delete(db: AsyncSession, org_id: int, user_id: int, conversation_id: int) -> None:
    # The messages go with it via ON DELETE CASCADE.
    conversation = await get(db, org_id, user_id, conversation_id)
    await db.delete(conversation)
    await db.commit()


async def list_messages(
    db: AsyncSession, org_id: int, user_id: int, conversation_id: int, page: int = 1, page_size: int = 50
) -> tuple[list[Message], int]:
    conversation = await get(db, org_id, user_id, conversation_id)
    return await Message.list_for_conversation(db, conversation.id, page=page, page_size=page_size)


async def add_message(
    db: AsyncSession, conversation: Conversation, role: MessageRole, content: str | None = None, **fields
) -> Message:
    """
    Append a turn and move the conversation's `last_message_at`, in one transaction.
    The API only ever passes MessageRole.USER; assistant and tool turns come from server code.
    `fields` are the optional Message columns (tool_calls, tool_call_id, tool_name, model, tokens).
    """
    message = Message(conversation_id=conversation.id, role=role, content=content, **fields)
    db.add(message)
    conversation.last_message_at = func.now()
    await db.commit()
    await db.refresh(message)
    await db.refresh(conversation)
    return message
