from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import Membership
from hr_minds.recruitment.exceptions import JobPostingNotFound
from hr_minds.recruitment.models import JobPosting, JobRequirement
from hr_minds.recruitment.schemas import JobPostingCreate, JobPostingUpdate


async def create(db: AsyncSession, membership: Membership, data: JobPostingCreate) -> JobPosting:
    posting = JobPosting(
        org_id=membership.org_id,
        created_by_id=membership.user_id,
        title=data.title,
        description=data.description,
        requirements=[JobRequirement(text=r.text, must_have=r.must_have) for r in data.requirements],
    )
    db.add(posting)
    await db.commit()
    await db.refresh(posting)  # no attribute_names: a narrower refresh expires the rest
    return posting


async def get(db: AsyncSession, org_id: int, job_posting_id: int) -> JobPosting:
    posting = await JobPosting.get(db, org_id, job_posting_id)
    if posting is None:
        raise JobPostingNotFound()
    return posting


async def list_for_org(db: AsyncSession, org_id: int, page: int = 1, page_size: int = 20) -> tuple[list[JobPosting], int]:
    return await JobPosting.list_for_org(db, org_id, page, page_size)


async def update(db: AsyncSession, org_id: int, job_posting_id: int, data: JobPostingUpdate) -> JobPosting:
    posting = await get(db, org_id, job_posting_id)
    if data.title is not None:
        posting.title = data.title
    if data.description is not None:
        posting.description = data.description
    if data.requirements is not None:
        rows = [{"text": r.text, "must_have": r.must_have} for r in data.requirements]
        await JobPosting.replace_requirements(db, posting.id, rows)
    await db.commit()
    # No attribute_names: that form expires the WHOLE object, then reloads only the
    # names given, leaving everything else (e.g. `modified`, created_by) expired and
    # prone to an implicit lazy load outside the async session's context on next access.
    await db.refresh(posting)
    return posting


async def delete(db: AsyncSession, org_id: int, job_posting_id: int) -> None:
    # Requirements and candidates go with it via ON DELETE CASCADE.
    posting = await get(db, org_id, job_posting_id)
    await db.delete(posting)
    await db.commit()
