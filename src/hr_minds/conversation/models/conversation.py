from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from hr_minds.settings.db import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    """
    A chat session. Private to the user who started it, inside the organization
    that was active at the time — every query filters on both `org_id` and `user_id`.

    `context_type` / `context_id` say what the chat is about (e.g. "job_posting", "12").
    There is deliberately no foreign key: this module knows nothing about other modules,
    so a context can outlive the thing it points at.
    """

    __table_args__ = (
        CheckConstraint("(context_type IS NULL) = (context_id IS NULL)", name="context_pair"),
    )

    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    context_type: Mapped[str | None] = mapped_column(String(50))
    context_id: Mapped[str | None] = mapped_column(String(64))
    # Starts at creation time and moves on every new message; the list sorts by it.
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @classmethod
    async def get(cls, db: AsyncSession, org_id: int, user_id: int, conversation_id: int) -> "Conversation | None":
        return await db.scalar(
            select(cls).where(cls.org_id == org_id, cls.user_id == user_id, cls.id == conversation_id)
        )

    @classmethod
    async def list_for_user(
        cls,
        db: AsyncSession,
        org_id: int,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        context_type: str | None = None,
        context_id: str | None = None,
    ) -> tuple[list["Conversation"], int]:
        where = [cls.org_id == org_id, cls.user_id == user_id]
        if context_type is not None:
            where.append(cls.context_type == context_type)
        if context_id is not None:
            where.append(cls.context_id == context_id)

        total = (await db.scalar(select(func.count()).select_from(cls).where(*where))) or 0
        items = list(
            await db.scalars(
                select(cls)
                .where(*where)
                .order_by(cls.last_message_at.desc(), cls.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total
