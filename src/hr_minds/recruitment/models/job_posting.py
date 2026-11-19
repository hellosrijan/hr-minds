from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hr_minds.settings.db import Base, TimestampMixin

if TYPE_CHECKING:
    from hr_minds.auth.models.user import User


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class WorkMode(StrEnum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


class JobPostingStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    ON_HOLD = "on_hold"
    CLOSED = "closed"


class JobSkill(Base, TimestampMixin):
    """
    One skill a JobPosting asks for. `name` is how it's shown; `name_normalized` is the
    lowercase form used to match it against resumes later.

    No relationship back to JobPosting: deleting a posting removes its skills via
    `ondelete="CASCADE"` alone.
    """

    job_posting_id: Mapped[int] = mapped_column(ForeignKey("job_posting.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    name_normalized: Mapped[str] = mapped_column(String(100), index=True)
    must_have: Mapped[bool] = mapped_column(default=False)
    # Years of this skill the job wants; None means the skill is listed without a minimum.
    min_years: Mapped[int | None]


class JobPosting(Base, TimestampMixin):
    """
    A job an organization is hiring for, as it would appear to a candidate: the company,
    where and how the work happens, the experience and skills wanted, and the pay.
    Candidates (resumes selected for it) are tracked separately in JobCandidate.
    """

    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    # The client the role is for. Recruiters post for several companies, so it's typed per posting.
    company_name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(100))

    employment_type: Mapped[EmploymentType] = mapped_column(String(20), default=EmploymentType.FULL_TIME)
    work_mode: Mapped[WorkMode] = mapped_column(String(20), default=WorkMode.ONSITE)
    # Null for remote roles that aren't tied to a place.
    location_city: Mapped[str | None] = mapped_column(String(100))
    location_region: Mapped[str | None] = mapped_column(String(100))
    location_country: Mapped[str | None] = mapped_column(String(100))

    experience_min_years: Mapped[int] = mapped_column(default=0)
    # Null means no upper limit.
    experience_max_years: Mapped[int | None]

    # Whole units of `salary_currency` (ISO 4217, e.g. "INR", "USD"). Null when not disclosed.
    salary_min: Mapped[int | None]
    salary_max: Mapped[int | None]
    salary_currency: Mapped[str | None] = mapped_column(String(3))

    openings: Mapped[int] = mapped_column(default=1)
    status: Mapped[JobPostingStatus] = mapped_column(String(20), default=JobPostingStatus.OPEN)

    created_by: Mapped["User"] = relationship(lazy="joined")
    # Read for responses; replacing the list on update is done with explicit
    # delete()/insert() in the service, not by reassigning this collection.
    # passive_deletes="all": when the posting is deleted, never null or delete these
    # children at the ORM level, even if they're already loaded — trust
    # `ondelete="CASCADE"` to remove them in the DB. Plain `passive_deletes=True`
    # isn't enough: it only skips loading children that aren't loaded yet.
    skills: Mapped[list["JobSkill"]] = relationship(
        lazy="selectin", order_by="JobSkill.id", passive_deletes="all"
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
    async def replace_skills(cls, db: AsyncSession, job_posting_id: int, rows: list[dict]) -> None:
        # Core-level DML, not delete(JobSkill): an ORM-enabled delete on a session that already
        # has these rows eager-loaded via `skills` tries to null their FK as a relationship
        # side effect instead of just deleting them, which fails the NOT NULL constraint.
        await db.execute(JobSkill.__table__.delete().where(JobSkill.job_posting_id == job_posting_id))
        if rows:
            await db.execute(JobSkill.__table__.insert(), [{"job_posting_id": job_posting_id, **r} for r in rows])
