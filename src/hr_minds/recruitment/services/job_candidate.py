from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.models import Membership
from hr_minds.media.models import LocalMedia
from hr_minds.recruitment.exceptions import CandidateAlreadySelected, JobCandidateNotFound, ResumeNotFound
from hr_minds.recruitment.models import JobCandidate, JobCandidateStatus
from hr_minds.recruitment.schemas import JobCandidateCreate, JobCandidateUpdate
from hr_minds.recruitment.services import job_posting as job_posting_service


async def select(
    db: AsyncSession, membership: Membership, job_posting_id: int, data: JobCandidateCreate
) -> JobCandidate:
    await job_posting_service.get(db, membership.org_id, job_posting_id)  # 404s if missing or another org's

    resume = await db.get(LocalMedia, data.local_media_id)
    if resume is None or resume.org_id != membership.org_id:
        raise ResumeNotFound()
    if await JobCandidate.find(db, job_posting_id, resume.id) is not None:
        raise CandidateAlreadySelected()

    candidate = JobCandidate(
        job_posting_id=job_posting_id,
        org_id=membership.org_id,
        local_media_id=resume.id,
        selected_by_id=membership.user_id,
        status=JobCandidateStatus.SHORTLISTED,
    )
    db.add(candidate)
    await db.commit()
    # No attribute_names: that form expires the WHOLE object, then reloads only the
    # names given, leaving everything else (e.g. `modified`) expired and prone to an
    # implicit lazy load outside the async session's context on next access.
    await db.refresh(candidate)
    return candidate


async def get(db: AsyncSession, org_id: int, job_posting_id: int, candidate_id: int) -> JobCandidate:
    candidate = await JobCandidate.get(db, org_id, job_posting_id, candidate_id)
    if candidate is None:
        raise JobCandidateNotFound()
    return candidate


async def list_for_posting(
    db: AsyncSession,
    org_id: int,
    job_posting_id: int,
    page: int = 1,
    page_size: int = 20,
    status: JobCandidateStatus | None = None,
) -> tuple[list[JobCandidate], int]:
    await job_posting_service.get(db, org_id, job_posting_id)  # 404s if missing or another org's
    return await JobCandidate.list_for_posting(db, org_id, job_posting_id, page, page_size, status)


async def update_status(
    db: AsyncSession, org_id: int, job_posting_id: int, candidate_id: int, data: JobCandidateUpdate
) -> JobCandidate:
    candidate = await get(db, org_id, job_posting_id, candidate_id)
    candidate.status = data.status
    await db.commit()
    await db.refresh(candidate)
    return candidate


async def remove(db: AsyncSession, org_id: int, job_posting_id: int, candidate_id: int) -> None:
    candidate = await get(db, org_id, job_posting_id, candidate_id)
    await db.delete(candidate)
    await db.commit()
