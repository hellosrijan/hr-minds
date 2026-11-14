from enum import StrEnum

from sqlalchemy import ForeignKey, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from hr_minds.settings.db import Base, TimestampMixin


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(Base, TimestampMixin):
    """
    One turn in a Conversation, in our own provider-neutral shape. The agent adapter
    converts to and from a provider's format, so switching provider needs no data migration.

    Only `user` messages come from clients; `assistant` and `tool` messages are written by
    server code, because everything stored here is replayed to the model as history.
    Order within a conversation is by `id`.
    """

    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), index=True)
    role: Mapped[MessageRole] = mapped_column(String(20))
    # Null for an assistant turn that is only tool calls.
    content: Mapped[str | None] = mapped_column(Text)
    # Assistant turns: [{"id": ..., "name": ..., "arguments": {...}}]
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSONB)
    # Tool turns: which call this answers, and by which tool.
    tool_call_id: Mapped[str | None] = mapped_column(String(100))
    tool_name: Mapped[str | None] = mapped_column(String(100))
    # Assistant turns: which model answered and what it cost. Can't be rebuilt later.
    model: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)

    @classmethod
    async def list_for_conversation(
        cls, db: AsyncSession, conversation_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list["Message"], int]:
        total = (
            await db.scalar(select(func.count()).select_from(cls).where(cls.conversation_id == conversation_id))
        ) or 0
        items = list(
            await db.scalars(
                select(cls)
                .where(cls.conversation_id == conversation_id)
                .order_by(cls.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total
