from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.settings.db import Base, TimestampMixin

if TYPE_CHECKING:
    from hr_minds.auth.models.user import User
    from hr_minds.media.models.local_media import LocalMedia


class JobCandidateStatus(StrEnum):
    SHORTLISTED = "shortlisted"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    HIRED = "hired"
    REJECTED = "rejected"


class JobCandidate(Base, TimestampMixin):
    """
    A resume selected for a JobPosting, and where it stands in the pipeline.
    `created` is when it was selected; `modified` moves when the status changes.

    No relationship back to JobPosting: it's never navigated from here, and
    deleting a posting removes its candidates via `ondelete="CASCADE"` alone.

    # ponytail: local_media_id cascades on delete, so a rescan that prunes a
    # removed file (see media/services/scanner.py) silently drops its
    # selections too. Denormalizing the file name/path here would survive
    # that, at the cost of a stale snapshot — add if it bites.
    """

    __table_args__ = (UniqueConstraint("job_posting_id", "local_media_id"),)

    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_posting.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    local_media_id: Mapped[int] = mapped_column(ForeignKey("local_media.id", ondelete="CASCADE"), index=True)
    status: Mapped[JobCandidateStatus] = mapped_column(String(20), default=JobCandidateStatus.SHORTLISTED)
    # SET NULL: a selection stays on record if whoever made it leaves the org.
    selected_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))

    resume: Mapped["LocalMedia"] = relationship(lazy="joined")
    selected_by: Mapped["User | None"] = relationship(lazy="joined")

    @classmethod
    async def get(cls, db: AsyncSession, org_id: int, job_posting_id: int, candidate_id: int) -> "JobCandidate | None":
        return await db.scalar(
            select(cls).where(cls.org_id == org_id, cls.job_posting_id == job_posting_id, cls.id == candidate_id)
        )

    @classmethod
    async def find(cls, db: AsyncSession, job_posting_id: int, local_media_id: int) -> "JobCandidate | None":
        return await db.scalar(
            select(cls).where(cls.job_posting_id == job_posting_id, cls.local_media_id == local_media_id)
        )

    @classmethod
    async def list_for_posting(
        cls,
        db: AsyncSession,
        org_id: int,
        job_posting_id: int,
        page: int = 1,
        page_size: int = 20,
        status: JobCandidateStatus | None = None,
    ) -> tuple[list["JobCandidate"], int]:
        where = [cls.org_id == org_id, cls.job_posting_id == job_posting_id]
        if status is not None:
            where.append(cls.status == status)
        total = (await db.scalar(select(func.count()).select_from(cls).where(*where))) or 0
        items = list(
            await db.scalars(
                select(cls).where(*where).order_by(cls.id).offset((page - 1) * page_size).limit(page_size)
            )
        )
        return items, total
