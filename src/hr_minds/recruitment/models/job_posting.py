from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.settings.db import Base, TimestampMixin

if TYPE_CHECKING:
    from hr_minds.auth.models.user import User


class JobRequirement(Base, TimestampMixin):
    """
    One requirement of a JobPosting, marked must-have or nice-to-have.

    No relationship back to JobPosting: it's never navigated from here, and
    deleting a posting removes its requirements via `ondelete="CASCADE"` alone,
    the same way Message needs no relationship back to Conversation.
    """

    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_posting.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(500))
    must_have: Mapped[bool] = mapped_column(default=False)


class JobPosting(Base, TimestampMixin):
    """
    A job an organization is hiring for, with its requirements. Candidates
    (resumes selected for it) are tracked separately in JobCandidate.
    """

    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)

    created_by: Mapped["User"] = relationship(lazy="joined")
    # Read for responses; replacing the list on update is done with explicit
    # delete()/insert() in the service, not by reassigning this collection.
    # passive_deletes="all": when the posting is deleted, never null or delete these
    # children at the ORM level, even if (as here, via selectin) they're already loaded
    # — trust `ondelete="CASCADE"` to remove them in the DB. Plain `passive_deletes=True`
    # isn't enough: it only skips loading children that aren't loaded yet.
    requirements: Mapped[list["JobRequirement"]] = relationship(
        lazy="selectin", order_by="JobRequirement.id", passive_deletes="all"
    )

    @classmethod
    async def get(cls, db: AsyncSession, org_id: int, job_posting_id: int) -> "JobPosting | None":
        return await db.scalar(select(cls).where(cls.org_id == org_id, cls.id == job_posting_id))

    @classmethod
    async def list_for_org(
        cls, db: AsyncSession, org_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list["JobPosting"], int]:
        total = (await db.scalar(select(func.count()).select_from(cls).where(cls.org_id == org_id))) or 0
        items = list(
            await db.scalars(
                select(cls)
                .where(cls.org_id == org_id)
                .order_by(cls.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    @classmethod
    async def replace_requirements(cls, db: AsyncSession, job_posting_id: int, rows: list[dict]) -> None:
        # Core-level DML, not delete(JobRequirement): an ORM-enabled delete on a session
        # that already has these rows eager-loaded via `requirements` tries to null their
        # FK as a relationship-disassociation side effect instead of just deleting them,
        # which fails the NOT NULL constraint. Plain Table statements skip that bookkeeping.
        await db.execute(JobRequirement.__table__.delete().where(JobRequirement.job_posting_id == job_posting_id))
        if rows:
            await db.execute(JobRequirement.__table__.insert(), [{"job_posting_id": job_posting_id, **r} for r in rows])
