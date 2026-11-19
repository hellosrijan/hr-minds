from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from hr_minds.auth.dependencies import require
from hr_minds.auth.models import Membership
from hr_minds.recruitment.models import JobCandidateStatus
from hr_minds.recruitment.schemas import JobCandidateCreate, JobCandidateRead, JobCandidateUpdate
from hr_minds.recruitment.services import job_candidate as job_candidate_service
from hr_minds.settings.db import get_db
from hr_minds.settings.features import FeatureSlug
from hr_minds.utils.pagination import PaginatedResponse

router = APIRouter(prefix="/recruitment/job-postings/{job_posting_id}/candidates", tags=["Recruitment"])

RECRUITMENT = FeatureSlug.RECRUITMENT


@router.post("", response_model=JobCandidateRead, status_code=status.HTTP_201_CREATED,
            summary="Select a resume for this job posting")
async def select_candidate(
    job_posting_id: int,
    data: JobCandidateCreate,
    membership: Membership = Depends(require(RECRUITMENT, "create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Select a resume from local media and attach it as a candidate for this job posting.
    """
    return job_candidate_service.to_read(await job_candidate_service.select(db, membership, job_posting_id, data))


@router.get("", response_model=PaginatedResponse[JobCandidateRead],
           summary="List candidates selected for this job posting (paginated)")
async def list_candidates(
    job_posting_id: int,
    status_filter: Annotated[JobCandidateStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    membership: Membership = Depends(require(RECRUITMENT, "read")),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[JobCandidateRead]:
    """
    List candidates attached to this job posting, with optional status filtering.
    """
    items, total = await job_candidate_service.list_for_posting(
        db, membership.org_id, job_posting_id, page, page_size, status_filter
    )
    return PaginatedResponse.create(items=[job_candidate_service.to_read(c) for c in items], total=total, page=page, page_size=page_size)


@router.patch("/{candidate_id}", response_model=JobCandidateRead, summary="Change a candidate's pipeline status")
async def update_candidate(
    job_posting_id: int,
    candidate_id: int,
    data: JobCandidateUpdate,
    membership: Membership = Depends(require(RECRUITMENT, "update")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a candidate's pipeline status (e.g. screened, interview, rejected, hired).
    """
    return job_candidate_service.to_read(await job_candidate_service.update_status(db, membership.org_id, job_posting_id, candidate_id, data))


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Remove a candidate from the pipeline (the resume file is untouched)")
async def remove_candidate(
    job_posting_id: int,
    candidate_id: int,
    membership: Membership = Depends(require(RECRUITMENT, "delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove a candidate from the recruitment pipeline. The underlying resume file remains untouched.
    """
    await job_candidate_service.remove(db, membership.org_id, job_posting_id, candidate_id)
